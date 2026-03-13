"""IBGE CEMPRE Employment Indicators Pipeline.

Source: IBGE SIDRA API — Table 6450 (CEMPRE - Cadastro Central de Empresas)
Format: JSON
Variables:
  707 — Pessoal ocupado total (Total employed persons)
  708 — Pessoal ocupado assalariado (Salaried employed persons)
  662 — Salário médio mensal (Average monthly salary in minimum wages)
Classification:
  c12762/117897 — Total CNAE (all economic sectors)
  c12762/117609 — Section J: Information and Communication (telecom proxy)

CEMPRE is an annual census of all formal enterprises in Brazil. It provides
ground-truth employment counts per municipality — a strong demand proxy for
broadband: municipalities with large formal workforces need connectivity.
"""
import logging
from typing import Any

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

# IBGE SIDRA API base for CEMPRE table 6450
SIDRA_BASE = "https://apisidra.ibge.gov.br/values/t/6450"

# All municipalities, variables 707 (total employed), 708 (salaried), 662 (avg salary)
# Total CNAE (all sectors): c12762/117897
URL_TOTAL = (
    f"{SIDRA_BASE}/n6/all/v/707,708,662/p/last%201/c12762/117897"
)

# All municipalities, variable 707 only
# Section J — Information and Communication: c12762/117609
URL_TELECOM = (
    f"{SIDRA_BASE}/n6/all/v/707/p/last%201/c12762/117609"
)

# SIDRA field mapping
# D1C = municipality code (7-digit IBGE), D1N = municipality name
# D2C = variable code, D2N = variable name
# D3C = year, V = value
VARIABLE_TOTAL_EMPLOYED = "707"
VARIABLE_SALARIED = "708"
VARIABLE_AVG_SALARY = "662"


class CAGEDEmploymentPipeline(BasePipeline):
    """Ingest IBGE CEMPRE formal employment indicators per municipality."""

    def __init__(self):
        super().__init__("caged_employment")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS employment_indicators (
                id SERIAL PRIMARY KEY,
                l2_id INTEGER REFERENCES admin_level_2(id),
                municipality_code VARCHAR(10),
                year INTEGER,
                month INTEGER,
                formal_jobs_total INTEGER,
                formal_jobs_telecom INTEGER,
                formal_jobs_services INTEGER,
                avg_salary_brl NUMERIC,
                net_hires INTEGER,
                source VARCHAR(50) DEFAULT 'ibge_cempre',
                UNIQUE (municipality_code, year, month)
            )
        """)
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM employment_indicators WHERE source = 'ibge_cempre'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        # Re-run if we have fewer than 5000 CEMPRE records (Brazil has ~5570 municipalities)
        return count < 5000

    def download(self) -> dict[str, Any]:
        """Fetch CEMPRE data from IBGE SIDRA API.

        Makes two API calls:
        1. Total employment (all CNAE sectors) — variables 707, 708, 662
        2. Telecom employment (Section J: Information and Communication) — variable 707

        Returns a dict with keys 'total' and 'telecom', each a list of records.
        """
        with PipelineHTTPClient(timeout=120) as http:
            logger.info("Fetching IBGE CEMPRE total employment data (table 6450)...")
            total_data = http.get_json(URL_TOTAL)
            if not isinstance(total_data, list) or len(total_data) < 2:
                raise RuntimeError(
                    f"IBGE SIDRA API returned unexpected data for total employment. "
                    f"Got {type(total_data).__name__} with {len(total_data) if isinstance(total_data, list) else 'N/A'} records. "
                    f"URL: {URL_TOTAL}"
                )
            # First record is the header row — skip it
            total_records = total_data[1:]
            logger.info(f"Received {len(total_records)} total employment records from SIDRA")

            logger.info("Fetching IBGE CEMPRE telecom employment data (Section J)...")
            telecom_data = http.get_json(URL_TELECOM)
            if not isinstance(telecom_data, list) or len(telecom_data) < 2:
                raise RuntimeError(
                    f"IBGE SIDRA API returned unexpected data for telecom employment. "
                    f"Got {type(telecom_data).__name__} with {len(telecom_data) if isinstance(telecom_data, list) else 'N/A'} records. "
                    f"URL: {URL_TELECOM}"
                )
            telecom_records = telecom_data[1:]
            logger.info(f"Received {len(telecom_records)} telecom employment records from SIDRA")

        return {"total": total_records, "telecom": telecom_records}

    def transform(self, raw_data: dict[str, Any]) -> pd.DataFrame:
        """Transform SIDRA JSON records into employment_indicators rows.

        Each SIDRA record has:
          D1C — 7-digit municipality IBGE code
          D2C — variable code (707, 708, 662)
          D3C — year
          V   — value (string, may be '-' or '...' for missing)
        """
        if not raw_data:
            return pd.DataFrame()

        total_records = raw_data["total"]
        telecom_records = raw_data["telecom"]

        # Build municipality code -> l2_id mapping from database
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, code FROM admin_level_2")
        # SIDRA D1C is 7-digit; admin_level_2.code may be 7-digit or need matching
        l2_map = {}
        for row in cur.fetchall():
            l2_id, code = row
            code_str = str(code).strip()
            l2_map[code_str] = l2_id
            # Also map 7-digit version if code is shorter (e.g., 6-digit)
            if len(code_str) == 7:
                l2_map[code_str[:6]] = l2_id
        cur.close()
        conn.close()

        # Parse total employment records into per-municipality dicts
        # Key: (municipality_code_7digit, year)
        municipality_data: dict[tuple[str, int], dict] = {}

        for record in total_records:
            muni_code = str(record.get("D1C", "")).strip()
            var_code = str(record.get("D2C", "")).strip()
            year_str = str(record.get("D3C", "")).strip()
            value_str = str(record.get("V", "")).strip()

            if not muni_code or not year_str:
                continue

            # Skip missing/suppressed values
            if value_str in ("", "-", "...", "X", "0"):
                parsed_value = 0
            else:
                try:
                    # SIDRA returns integers as strings, salaries may have decimals
                    parsed_value = float(value_str.replace(",", "."))
                except (ValueError, TypeError):
                    parsed_value = 0

            try:
                year = int(year_str)
            except (ValueError, TypeError):
                continue

            key = (muni_code, year)
            if key not in municipality_data:
                municipality_data[key] = {
                    "municipality_code_7d": muni_code,
                    "year": year,
                    "formal_jobs_total": 0,
                    "formal_jobs_salaried": 0,
                    "avg_salary_brl": 0.0,
                    "formal_jobs_telecom": 0,
                }

            entry = municipality_data[key]
            if var_code == VARIABLE_TOTAL_EMPLOYED:
                entry["formal_jobs_total"] = int(parsed_value)
            elif var_code == VARIABLE_SALARIED:
                entry["formal_jobs_salaried"] = int(parsed_value)
            elif var_code == VARIABLE_AVG_SALARY:
                # Variable 662 is in minimum wages; convert to BRL
                # 2021 minimum wage was R$1,100
                entry["avg_salary_brl"] = round(parsed_value * 1100.0, 2)

        # Parse telecom employment records
        for record in telecom_records:
            muni_code = str(record.get("D1C", "")).strip()
            year_str = str(record.get("D3C", "")).strip()
            value_str = str(record.get("V", "")).strip()

            if not muni_code or not year_str:
                continue

            if value_str in ("", "-", "...", "X"):
                parsed_value = 0
            else:
                try:
                    parsed_value = int(float(value_str.replace(",", ".")))
                except (ValueError, TypeError):
                    parsed_value = 0

            try:
                year = int(year_str)
            except (ValueError, TypeError):
                continue

            key = (muni_code, year)
            if key in municipality_data:
                municipality_data[key]["formal_jobs_telecom"] = parsed_value
            else:
                # Municipality only has telecom data but no total — still record it
                municipality_data[key] = {
                    "municipality_code_7d": muni_code,
                    "year": year,
                    "formal_jobs_total": 0,
                    "formal_jobs_salaried": 0,
                    "avg_salary_brl": 0.0,
                    "formal_jobs_telecom": parsed_value,
                }

        # Build final rows, mapping 7-digit codes to l2_id
        rows = []
        unmatched = 0
        for (muni_code_7d, year), data in municipality_data.items():
            # Try to match the 7-digit IBGE code to admin_level_2
            l2_id = l2_map.get(muni_code_7d)
            if l2_id is None:
                # Try 6-digit version (some IBGE codes drop the check digit)
                l2_id = l2_map.get(muni_code_7d[:6])
            if l2_id is None:
                unmatched += 1
                continue

            rows.append({
                "l2_id": l2_id,
                "municipality_code": muni_code_7d,
                "year": year,
                "month": 12,  # CEMPRE is annual; use December as snapshot month
                "formal_jobs_total": data["formal_jobs_total"],
                "formal_jobs_telecom": data["formal_jobs_telecom"],
                "formal_jobs_services": data["formal_jobs_salaried"],  # salaried as services proxy
                "avg_salary_brl": data["avg_salary_brl"],
                "net_hires": 0,  # CEMPRE is a stock variable, not a flow — no net hires
                "source": "ibge_cempre",
            })

        if unmatched > 0:
            logger.warning(
                f"{unmatched} municipality codes from SIDRA could not be matched to admin_level_2"
            )

        self.rows_processed = len(rows)
        logger.info(
            f"Transformed {len(rows)} employment records "
            f"({unmatched} unmatched municipalities skipped)"
        )
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def load(self, data: pd.DataFrame) -> None:
        if data.empty:
            return

        conn = self._get_connection()
        cur = conn.cursor()
        loaded = 0

        for _, row in data.iterrows():
            try:
                cur.execute("SAVEPOINT row_sp")
                cur.execute("""
                    INSERT INTO employment_indicators
                        (l2_id, municipality_code, year, month,
                         formal_jobs_total, formal_jobs_telecom, formal_jobs_services,
                         avg_salary_brl, net_hires, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (municipality_code, year, month) DO UPDATE SET
                        l2_id = EXCLUDED.l2_id,
                        formal_jobs_total = EXCLUDED.formal_jobs_total,
                        formal_jobs_telecom = EXCLUDED.formal_jobs_telecom,
                        formal_jobs_services = EXCLUDED.formal_jobs_services,
                        avg_salary_brl = EXCLUDED.avg_salary_brl,
                        net_hires = EXCLUDED.net_hires,
                        source = EXCLUDED.source
                """, (
                    int(row["l2_id"]),
                    str(row["municipality_code"]),
                    int(row["year"]),
                    int(row["month"]),
                    int(row.get("formal_jobs_total", 0)),
                    int(row.get("formal_jobs_telecom", 0)),
                    int(row.get("formal_jobs_services", 0)),
                    float(row.get("avg_salary_brl", 0)),
                    int(row.get("net_hires", 0)),
                    str(row.get("source", "ibge_cempre")),
                ))
                loaded += 1
                cur.execute("RELEASE SAVEPOINT row_sp")
            except Exception as e:
                logger.warning(f"Failed to load employment row: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT row_sp")

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} IBGE CEMPRE employment records")

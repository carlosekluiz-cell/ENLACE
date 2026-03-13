"""IBGE MUNIC (Pesquisa de Informacoes Basicas Municipais) Pipeline.

Source: IBGE SIDRA API — Table 5882 (Plano Diretor) and Table 5883 (Legislation)
Format: JSON from https://apisidra.ibge.gov.br/
Fields: Plano Diretor status, zoning law, building code, digital governance

Municipalities with a Plano Diretor and digital governance programs are
easier to deploy in — faster permitting, clearer zoning for tower placement.
This feeds into opportunity scoring as a regulatory-ease factor.
"""
import logging
from typing import Optional

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

# IBGE SIDRA API endpoints
# Table 5882: Plano Diretor status per municipality
# n6/all = all municipalities, v/603 = count, p/last%201 = most recent period
# c1480/all = all Plano Diretor classification categories
SIDRA_TABLE_5882_URL = (
    "https://apisidra.ibge.gov.br/values"
    "/t/5882/n6/all/v/603/p/last%201/c1480/all"
)

# Table 5883: Legislation instruments per municipality
# c1481 = legislation classification (zoning, building code, etc.)
SIDRA_TABLE_5883_URL = (
    "https://apisidra.ibge.gov.br/values"
    "/t/5883/n6/all/v/603/p/last%201/c1481/all"
)


class IBGEMUNICPipeline(BasePipeline):
    """Ingest IBGE MUNIC municipal planning and governance data."""

    def __init__(self):
        super().__init__("ibge_munic")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS municipal_planning (
                id SERIAL PRIMARY KEY,
                l2_id INTEGER REFERENCES admin_level_2(id),
                municipality_code VARCHAR(10),
                has_plano_diretor BOOLEAN DEFAULT FALSE,
                plano_diretor_year INTEGER,
                has_zoning_law BOOLEAN DEFAULT FALSE,
                has_building_code BOOLEAN DEFAULT FALSE,
                has_digital_governance BOOLEAN DEFAULT FALSE,
                munic_year INTEGER,
                source VARCHAR(50) DEFAULT 'ibge_munic',
                UNIQUE (municipality_code, munic_year)
            )
        """)
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM municipal_planning")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 100

    def download(self) -> dict:
        """Download real data from IBGE SIDRA API tables 5882 and 5883.

        Returns a dict with keys 'plano_diretor' and 'legislation',
        each containing the raw JSON list from the SIDRA API.
        Raises on failure — never generates synthetic data.
        """
        result: dict = {}

        with PipelineHTTPClient(timeout=300) as http:
            # --- Table 5882: Plano Diretor ---
            logger.info("Downloading IBGE SIDRA table 5882 (Plano Diretor)...")
            try:
                raw_5882 = http.get_json(SIDRA_TABLE_5882_URL)
                if not isinstance(raw_5882, list) or len(raw_5882) < 2:
                    raise ValueError(
                        f"SIDRA table 5882 returned unexpected data: "
                        f"type={type(raw_5882).__name__}, len={len(raw_5882) if isinstance(raw_5882, list) else 'N/A'}"
                    )
                # First record is the header row — skip it
                result["plano_diretor"] = raw_5882[1:]
                logger.info(
                    f"Downloaded {len(result['plano_diretor'])} records from SIDRA table 5882"
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to download IBGE SIDRA table 5882 (Plano Diretor): {e}"
                ) from e

            # --- Table 5883: Legislation ---
            logger.info("Downloading IBGE SIDRA table 5883 (Legislation)...")
            try:
                raw_5883 = http.get_json(SIDRA_TABLE_5883_URL)
                if not isinstance(raw_5883, list) or len(raw_5883) < 2:
                    raise ValueError(
                        f"SIDRA table 5883 returned unexpected data: "
                        f"type={type(raw_5883).__name__}, len={len(raw_5883) if isinstance(raw_5883, list) else 'N/A'}"
                    )
                result["legislation"] = raw_5883[1:]
                logger.info(
                    f"Downloaded {len(result['legislation'])} records from SIDRA table 5883"
                )
            except Exception as e:
                # Legislation data is supplementary; log warning but continue
                logger.warning(
                    f"Failed to download IBGE SIDRA table 5883 (Legislation): {e}. "
                    f"Legislation fields (zoning, building code, digital governance) will be NULL."
                )
                result["legislation"] = None

        return result

    def transform(self, raw_data: dict) -> pd.DataFrame:
        """Parse SIDRA API responses and build the municipal_planning DataFrame.

        For table 5882, each record has:
            D1C — 7-digit municipality code
            D4N — classification name (e.g. "Sim", "Nao", "Total")
            V   — "1" if the municipality matches that classification

        We look for records where D4N contains "Sim" (has Plano Diretor)
        and V == "1".

        For table 5883 (legislation), we look for similar patterns for
        zoning law, building code, and digital governance categories.
        """
        if not raw_data:
            return pd.DataFrame()

        # Build l2_id lookup from admin_level_2.code
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, code FROM admin_level_2")
        # SIDRA uses 7-digit codes; admin_level_2.code may be 6 or 7 digits
        l2_map = {}
        for row in cur.fetchall():
            code_str = str(row[1]).strip()
            l2_map[code_str] = row[0]
        cur.close()
        conn.close()

        # --- Parse table 5882: Plano Diretor ---
        plano_diretor_records = raw_data.get("plano_diretor", [])
        # Track which municipalities have Plano Diretor = "Sim"
        plano_diretor_yes: set = set()
        # Track the survey year from D3N
        munic_year: Optional[int] = None
        # Track all municipality codes seen
        all_municipalities: set = set()

        for record in plano_diretor_records:
            muni_code = str(record.get("D1C", "")).strip()
            classification = str(record.get("D4N", "")).strip()
            value = str(record.get("V", "")).strip()

            if not muni_code or len(muni_code) < 6:
                continue

            all_municipalities.add(muni_code)

            # Extract the survey year from the first valid record
            if munic_year is None:
                year_str = str(record.get("D3N", "")).strip()
                if year_str.isdigit() and len(year_str) == 4:
                    munic_year = int(year_str)
                else:
                    # Try D3C (period code) — sometimes it is the year
                    d3c = str(record.get("D3C", "")).strip()
                    if d3c.isdigit() and len(d3c) == 4:
                        munic_year = int(d3c)

            # "Sim" means the municipality HAS a Plano Diretor
            if "Sim" in classification and value == "1":
                plano_diretor_yes.add(muni_code)

        if munic_year is None:
            munic_year = 2021  # fallback
        logger.info(
            f"MUNIC survey year: {munic_year}. "
            f"Municipalities with Plano Diretor: {len(plano_diretor_yes)} / {len(all_municipalities)}"
        )

        # --- Parse table 5883: Legislation ---
        legislation_records = raw_data.get("legislation")
        has_zoning: dict = {}       # muni_code -> bool
        has_building: dict = {}     # muni_code -> bool
        has_digital_gov: dict = {}  # muni_code -> bool

        if legislation_records:
            for record in legislation_records:
                muni_code = str(record.get("D1C", "")).strip()
                classification = str(record.get("D4N", "")).strip().lower()
                value = str(record.get("V", "")).strip()

                if not muni_code or len(muni_code) < 6:
                    continue

                if value != "1":
                    continue

                # Map SIDRA legislation categories to our fields.
                # The exact category names in table 5883 may vary;
                # we use substring matching for robustness.
                cl = classification
                if "zoneamento" in cl or "uso" in cl and "solo" in cl:
                    has_zoning[muni_code] = True
                elif "obra" in cl or "edifica" in cl or ("codigo" in cl and "obra" in cl):
                    has_building[muni_code] = True
                elif "digital" in cl or "governo eletr" in cl or "tecnologia" in cl:
                    has_digital_gov[muni_code] = True

            logger.info(
                f"Legislation data: zoning={len(has_zoning)}, "
                f"building_code={len(has_building)}, digital_gov={len(has_digital_gov)}"
            )
        else:
            logger.info(
                "No legislation data from table 5883; "
                "zoning/building/digital_governance fields will be NULL."
            )

        # --- Build output rows ---
        rows = []
        for muni_code in all_municipalities:
            # Map the 7-digit SIDRA code to l2_id
            l2_id = l2_map.get(muni_code)
            if not l2_id:
                # Try truncating to 6 digits (some IBGE codes drop the check digit)
                l2_id = l2_map.get(muni_code[:6])
            if not l2_id:
                continue

            has_pd = muni_code in plano_diretor_yes

            # If legislation data was NOT available, use None (NULL) instead of False
            zoning_val = has_zoning.get(muni_code) if legislation_records else None
            building_val = has_building.get(muni_code) if legislation_records else None
            digital_val = has_digital_gov.get(muni_code) if legislation_records else None

            # If legislation data WAS available but this municipality wasn't
            # flagged, it means "No" (False) for that category
            if legislation_records:
                if zoning_val is None:
                    zoning_val = False
                if building_val is None:
                    building_val = False
                if digital_val is None:
                    digital_val = False

            rows.append({
                "l2_id": l2_id,
                "municipality_code": muni_code,
                "has_plano_diretor": has_pd,
                "plano_diretor_year": munic_year if has_pd else None,
                "has_zoning_law": zoning_val,
                "has_building_code": building_val,
                "has_digital_governance": digital_val,
                "munic_year": munic_year,
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} municipal planning records from real IBGE data")
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
                    INSERT INTO municipal_planning
                        (l2_id, municipality_code, has_plano_diretor, plano_diretor_year,
                         has_zoning_law, has_building_code, has_digital_governance,
                         munic_year, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (municipality_code, munic_year) DO UPDATE SET
                        l2_id = EXCLUDED.l2_id,
                        has_plano_diretor = EXCLUDED.has_plano_diretor,
                        plano_diretor_year = EXCLUDED.plano_diretor_year,
                        has_zoning_law = EXCLUDED.has_zoning_law,
                        has_building_code = EXCLUDED.has_building_code,
                        has_digital_governance = EXCLUDED.has_digital_governance,
                        source = EXCLUDED.source
                """, (
                    int(row["l2_id"]),
                    str(row["municipality_code"]),
                    bool(row["has_plano_diretor"]),
                    int(row["plano_diretor_year"]) if pd.notna(row.get("plano_diretor_year")) else None,
                    bool(row["has_zoning_law"]) if pd.notna(row.get("has_zoning_law")) else None,
                    bool(row["has_building_code"]) if pd.notna(row.get("has_building_code")) else None,
                    bool(row["has_digital_governance"]) if pd.notna(row.get("has_digital_governance")) else None,
                    int(row.get("munic_year", 2021)),
                    "ibge_munic",
                ))
                loaded += 1
                cur.execute("RELEASE SAVEPOINT row_sp")
            except Exception as e:
                logger.warning(f"Failed to load planning row: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT row_sp")

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} municipal planning records from IBGE SIDRA")

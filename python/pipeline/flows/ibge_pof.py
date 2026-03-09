"""IBGE POF (Pesquisa de Orcamentos Familiares) pipeline.

Source: IBGE SIDRA API (Agregado 7462 — POF 2017-2018)
URL: https://servicodados.ibge.gov.br/api/v3/agregados/7462
Format: REST JSON
Fields: household expenditure on telecommunications per state

POF data reveals how much families spend on telecommunications,
a direct indicator of willingness-to-pay and market sizing for ISPs.
The data is available at state level (UF).
"""
import logging

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs, STATE_ABBREVIATIONS
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)


class IBGEPOFPipeline(BasePipeline):
    """Ingest IBGE POF household expenditure data."""

    def __init__(self):
        super().__init__("ibge_pof")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM economic_indicators WHERE source = 'ibge_pof'"
        )
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 27  # 27 UFs

    def download(self) -> list[dict]:
        """Fetch POF expenditure data from IBGE SIDRA API.

        POF 2017-2018 (Agregado 7462):
        - Variavel 6932: despesa media mensal familiar (BRL)
        - Tipos de despesa include: comunicacao/telecomunicacao

        We also fetch the general expenditure breakdown by category.
        """
        with PipelineHTTPClient(timeout=120) as http:
            all_data = []

            # POF: average monthly household expenditure by state
            # Agregado 7462, variable 6932 (média mensal), by UF
            logger.info("Fetching POF household expenditure from IBGE SIDRA...")
            try:
                data = http.get_json(
                    f"{self.urls.ibge_api_v3}/agregados/7462"
                    "/periodos/-1/variaveis/6932"
                    "?localidades=N3[all]&view=flat"
                )
                if isinstance(data, list):
                    all_data.extend(data)
                    logger.info(f"Fetched {len(data)} POF records")
            except Exception as e:
                logger.warning(f"POF primary fetch failed: {e}")

            if not all_data:
                # Fallback: try POF telecom-specific expenditure
                # Agregado 7468 (despesas por grupo)
                logger.info("Trying POF expenditure by group...")
                try:
                    data = http.get_json(
                        f"{self.urls.ibge_api_v3}/agregados/7468"
                        "/periodos/-1/variaveis/6932"
                        "?localidades=N3[all]&view=flat"
                    )
                    if isinstance(data, list):
                        all_data.extend(data)
                except Exception as e:
                    logger.warning(f"POF group fetch failed: {e}")

            if not all_data:
                # Final fallback: PNAD Contínua internet access
                logger.info("Using PNAD Contínua internet access proxy...")
                try:
                    data = http.get_json(
                        f"{self.urls.ibge_api_v3}/agregados/7432"
                        "/periodos/-1/variaveis/10163"
                        "?localidades=N3[all]&view=flat"
                    )
                    if isinstance(data, list):
                        all_data = data
                except Exception as e:
                    logger.warning(f"PNAD internet proxy failed: {e}")

            logger.info(f"Total POF records: {len(all_data)}")
            return all_data

    def validate_raw(self, data: list[dict]) -> None:
        if not data:
            raise ValueError("No POF data returned from IBGE SIDRA")
        logger.info(f"Validating {len(data)} POF records")

    def transform(self, raw_data: list[dict]) -> pd.DataFrame:
        """Transform IBGE SIDRA flat-view records into economic_indicators rows."""
        rows = []
        for record in raw_data:
            localidade = record.get("localidade", {})
            loc_id = str(localidade.get("id", ""))

            # State-level data: 2-digit IBGE code
            if not loc_id or len(loc_id) != 2:
                continue

            value_str = record.get("valor", record.get("V", ""))
            try:
                value = float(str(value_str).replace(",", "."))
            except (ValueError, TypeError):
                continue

            period = record.get("periodo", {})
            year_str = str(period.get("id", "2018") if isinstance(period, dict) else period)
            try:
                year = int(year_str[:4])
            except (ValueError, TypeError):
                year = 2018

            variable = record.get("variavel", "")
            var_name = variable if isinstance(variable, str) else str(variable)

            state_abbrev = STATE_ABBREVIATIONS.get(loc_id, loc_id)

            rows.append({
                "state_code": loc_id,
                "state_abbrev": state_abbrev,
                "year": year,
                "value": value,
                "variable": var_name,
                "source": "ibge_pof",
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} POF records")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        if data.empty:
            logger.warning("No POF data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        # POF is state-level data — store in economic_indicators
        # using l2_id=NULL for state-level, with state in sector_breakdown
        loaded = 0
        for _, row in data.iterrows():
            sector_data = {
                "state_abbrev": row["state_abbrev"],
                "variable": row["variable"],
                "pof_value": row["value"],
            }

            # Find any municipality in this state as reference (first one)
            cur.execute(
                "SELECT id FROM admin_level_2 WHERE state_abbrev = %s LIMIT 1",
                (row["state_abbrev"],),
            )
            result = cur.fetchone()
            if not result:
                continue

            # Use l2_id of first municipality in state; store state-wide data
            # Using ON CONFLICT to handle re-runs
            import json
            cur.execute("""
                INSERT INTO economic_indicators (l2_id, year, source, sector_breakdown)
                VALUES (%s, %s, 'ibge_pof', %s)
                ON CONFLICT (l2_id, year)
                DO UPDATE SET sector_breakdown = COALESCE(economic_indicators.sector_breakdown, '{}'::jsonb) || EXCLUDED.sector_breakdown
            """, (result[0], row["year"], json.dumps(sector_data)))
            loaded += 1

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} POF records")

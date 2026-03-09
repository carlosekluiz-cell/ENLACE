"""ANP fuel sales pipeline.

Source: Agencia Nacional do Petroleo (ANP)
URL: https://dados.gov.br/dados/conjuntos-dados/venda-de-derivados-de-petroleo-e-biocombustiveis
Format: CSV via CKAN (dados.gov.br)
Fields: municipality code, fuel type, volume sold (m3), year/month

Fuel sales data is a proxy for economic activity at municipal level.
Municipalities with high fuel consumption tend to have strong commercial
activity — relevant for ISP market sizing and demand estimation.
"""
import logging

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)


class ANPFuelPipeline(BasePipeline):
    """Ingest ANP fuel sales data per municipality."""

    def __init__(self):
        super().__init__("anp_fuel")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM economic_indicators WHERE source = 'anp_fuel'"
        )
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 100

    def download(self) -> pd.DataFrame:
        """Fetch fuel sales data from ANP via dados.gov.br CKAN.

        ANP publishes monthly fuel sales by municipality through the
        Brazilian open data portal (dados.gov.br).
        """
        with PipelineHTTPClient(timeout=180) as http:
            logger.info("Resolving ANP fuel dataset from dados.gov.br...")

            try:
                # Try the main CKAN dataset
                url = http.resolve_ckan_resource_url(
                    "venda-de-derivados-de-petroleo-e-biocombustiveis",
                    resource_format="CSV",
                )
                logger.info(f"Downloading ANP fuel CSV from: {url}")
                df = http.get_csv(url, sep=";", encoding="latin-1")
                logger.info(f"Downloaded {len(df)} rows from ANP")
                return df
            except Exception as e:
                logger.warning(f"ANP CKAN primary failed: {e}")

            try:
                # Fallback: try alternate dataset ID
                url = http.resolve_ckan_resource_url(
                    "vendas-anuais-de-derivados-de-petroleo-por-municipio",
                    resource_format="CSV",
                )
                logger.info(f"Trying alternate ANP dataset: {url}")
                df = http.get_csv(url, sep=";", encoding="latin-1")
                logger.info(f"Downloaded {len(df)} rows from ANP (alternate)")
                return df
            except Exception as e:
                logger.warning(f"ANP alternate CKAN failed: {e}")

            # Final fallback: aggregate from IBGE SIDRA industrial production proxy
            logger.info("Using IBGE industrial production proxy...")
            try:
                data = http.get_json(
                    "https://servicodados.ibge.gov.br/api/v3/agregados/5938"
                    "/periodos/-1/variaveis/37"
                    "?localidades=N6[all]&view=flat"
                )
                if isinstance(data, list):
                    rows = []
                    for r in data:
                        loc = r.get("localidade", {})
                        rows.append({
                            "MUNICIPIO": loc.get("nome", ""),
                            "CODIGO_MUNICIPIO": str(loc.get("id", "")),
                            "VALOR": r.get("valor", "0"),
                            "ANO": "2021",
                            "COMBUSTIVEL": "proxy_pib",
                        })
                    return pd.DataFrame(rows)
            except Exception as e:
                logger.warning(f"IBGE proxy failed: {e}")

            return pd.DataFrame()

    def validate_raw(self, data) -> None:
        if isinstance(data, pd.DataFrame) and data.empty:
            raise ValueError("No fuel sales data returned from any source")
        logger.info(f"Validating {len(data)} fuel records")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Aggregate fuel sales by municipality and year."""
        if raw_data.empty:
            return pd.DataFrame()

        # Identify columns (ANP CSVs have varying column names)
        cols = {c.upper().strip(): c for c in raw_data.columns}

        code_col = None
        for candidate in ["CODIGO_MUNICIPIO", "CÓDIGO MUNICÍPIO", "COD_MUNICIPIO", "MUNICIPIO_IBGE"]:
            if candidate.upper() in cols:
                code_col = cols[candidate.upper()]
                break

        year_col = None
        for candidate in ["ANO", "YEAR", "PERIODO"]:
            if candidate.upper() in cols:
                year_col = cols[candidate.upper()]
                break

        volume_col = None
        for candidate in ["VENDAS", "VOLUME", "VALOR", "QTD", "QUANTIDADE"]:
            if candidate.upper() in cols:
                volume_col = cols[candidate.upper()]
                break

        fuel_col = None
        for candidate in ["PRODUTO", "COMBUSTIVEL", "COMBUSTÍVEL", "TIPO"]:
            if candidate.upper() in cols:
                fuel_col = cols[candidate.upper()]
                break

        if not code_col:
            logger.warning(f"Could not identify municipality code column. Columns: {list(raw_data.columns)}")
            return pd.DataFrame()

        rows = []
        for _, record in raw_data.iterrows():
            code = str(record.get(code_col, "")).strip()
            if not code or len(code) < 6:
                continue
            code = code[:7]

            year = 2022
            if year_col:
                try:
                    year = int(str(record.get(year_col, "2022"))[:4])
                except (ValueError, TypeError):
                    pass

            volume = 0
            if volume_col:
                try:
                    vol_str = str(record.get(volume_col, "0")).replace(",", ".").replace(" ", "")
                    volume = float(vol_str)
                except (ValueError, TypeError):
                    pass

            fuel_type = str(record.get(fuel_col, "total")) if fuel_col else "total"

            rows.append({
                "municipality_code": code,
                "year": year,
                "fuel_type": fuel_type,
                "volume": volume,
                "source": "anp_fuel",
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} fuel sales records")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        if data.empty:
            logger.warning("No fuel sales data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        # Aggregate by municipality/year and store in economic_indicators
        import json
        loaded = 0
        grouped = data.groupby(["municipality_code", "year"])
        for (code, year), group in grouped:
            # Resolve l2_id
            cur.execute(
                "SELECT id FROM admin_level_2 WHERE code = %s LIMIT 1",
                (code,),
            )
            result = cur.fetchone()
            if not result:
                continue

            l2_id = result[0]
            total_volume = group["volume"].sum()

            # Breakdown by fuel type
            fuel_breakdown = {}
            for _, row in group.iterrows():
                ft = row["fuel_type"]
                fuel_breakdown[ft] = fuel_breakdown.get(ft, 0) + row["volume"]

            sector_data = {
                "anp_total_volume_m3": total_volume,
                "anp_fuel_breakdown": fuel_breakdown,
            }

            cur.execute("""
                INSERT INTO economic_indicators (l2_id, year, source, sector_breakdown)
                VALUES (%s, %s, 'anp_fuel', %s)
                ON CONFLICT (l2_id, year)
                DO UPDATE SET sector_breakdown = COALESCE(economic_indicators.sector_breakdown, '{}'::jsonb) || EXCLUDED.sector_breakdown
            """, (l2_id, year, json.dumps(sector_data)))
            loaded += 1

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} fuel sales records")

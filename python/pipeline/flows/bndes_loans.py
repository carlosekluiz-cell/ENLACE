"""BNDES telecom loans pipeline.

Source: BNDES Open Data (dadosabertos.bndes.gov.br)
URL: https://dadosabertos.bndes.gov.br/dataset/operacoes-financiamento
Format: CSV via direct download / CKAN API
Key fields: borrower CNPJ, sector (CNAE), contract value, disbursed amount,
            municipality code, interest rate, term

BNDES (Banco Nacional de Desenvolvimento Economico e Social) is Brazil's
national development bank. Its telecom loan portfolio reveals which ISPs
are investing in network expansion, the scale of their CAPEX plans, and
where new infrastructure is being financed.

We filter for CNAE sector 61xx (Telecomunicações) to extract telecom-specific
loans. Borrower CNPJs are mapped to existing provider records where possible.

Schedule: Monthly (1st at 05:30 UTC)
"""
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient, get_cache_path

logger = logging.getLogger(__name__)

BNDES_CKAN_DATASET = "operacoes-financiamento"
BNDES_CKAN_BASE = "https://dadosabertos.bndes.gov.br/api/3/action"

# Direct CSV URL (confirmed working)
BNDES_DIRECT_CSV_URL = (
    "https://dadosabertos.bndes.gov.br/dataset/"
    "10e21ad1-568e-45e5-a8af-43f2c05ef1a2/resource/"
    "6f56b78c-510f-44b6-8274-78a5b7e931f4/download/"
    "operacoes-financiamento-operacoes-nao-automaticas.csv"
)

# CNAE 61xx = Telecomunicações
TELECOM_CNAE_PREFIX = "61"


class BNDESLoansPipeline(BasePipeline):
    """Ingest BNDES telecom financing operations from open data.

    Downloads the full BNDES operations CSV via their open data portal,
    filters for telecom sector (CNAE 61xx or description containing
    "telecomunic"), maps borrower CNPJs to known ISP providers, resolves
    municipality codes to l2_id, and loads the data into the bndes_loans
    table.

    Raises an error if all download sources fail.
    """

    def __init__(self):
        super().__init__("bndes_loans")

    def check_for_updates(self) -> bool:
        """Create the bndes_loans table if needed and check for staleness."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bndes_loans (
                id SERIAL PRIMARY KEY,
                borrower_cnpj VARCHAR(20),
                borrower_name VARCHAR(300),
                provider_id INTEGER REFERENCES providers(id),
                sector VARCHAR(50),
                contract_value_brl NUMERIC,
                disbursed_brl NUMERIC,
                interest_rate NUMERIC,
                term_months INTEGER,
                municipality_code VARCHAR(10),
                l2_id INTEGER REFERENCES admin_level_2(id),
                contract_date DATE,
                source VARCHAR(50),
                UNIQUE(borrower_cnpj, contract_date)
            )
        """)
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM bndes_loans")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()

        # Run if we have fewer than expected telecom loans
        return count < 50

    def download(self) -> pd.DataFrame:
        """Download BNDES financing operations CSV.

        Primary source: confirmed working direct CSV URL.
        Fallback: CKAN API resolution from BNDES open data portal.

        Raises RuntimeError if all sources fail.
        """
        with PipelineHTTPClient(timeout=300) as http:
            # Primary: direct CSV URL (confirmed working)
            try:
                logger.info(
                    "Downloading BNDES operations CSV from direct URL..."
                )
                df = http.get_csv(
                    BNDES_DIRECT_CSV_URL, sep=";", encoding="latin-1"
                )
                logger.info(
                    f"Downloaded {len(df)} BNDES operation records "
                    f"from direct URL"
                )
                return df
            except Exception as e:
                logger.warning(f"BNDES direct CSV download failed: {e}")

            # Fallback: CKAN API resolution
            try:
                logger.info(
                    "Resolving BNDES operations dataset from CKAN API..."
                )
                csv_url = http.resolve_ckan_resource_url(
                    BNDES_CKAN_DATASET,
                    resource_format="CSV",
                    ckan_base=BNDES_CKAN_BASE,
                )
                logger.info(
                    f"Downloading BNDES operations CSV from CKAN: {csv_url}"
                )
                df = http.get_csv(csv_url, sep=";", encoding="latin-1")
                logger.info(
                    f"Downloaded {len(df)} BNDES operation records from CKAN"
                )
                return df
            except Exception as e:
                logger.warning(f"BNDES CKAN resolution failed: {e}")

            # Fallback: dados.gov.br CKAN mirror
            try:
                csv_url = http.resolve_ckan_resource_url(
                    "operacoes-de-financiamento-do-bndes",
                    resource_format="CSV",
                )
                logger.info(
                    f"Trying dados.gov.br mirror: {csv_url}"
                )
                df = http.get_csv(csv_url, sep=";", encoding="latin-1")
                logger.info(
                    f"Downloaded {len(df)} records from dados.gov.br mirror"
                )
                return df
            except Exception as e:
                logger.warning(f"dados.gov.br BNDES mirror failed: {e}")

            # All sources exhausted - raise error
            raise RuntimeError(
                "All BNDES data sources failed. Cannot proceed without "
                "real data. Tried: direct CSV URL, BNDES CKAN API, "
                "dados.gov.br mirror."
            )

    def validate_raw(self, data: pd.DataFrame) -> None:
        """Validate that we have BNDES loan data to process."""
        if isinstance(data, pd.DataFrame) and data.empty:
            raise ValueError("No BNDES loan data returned from any source")
        logger.info(f"Validating {len(data)} BNDES operation records")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Filter for telecom sector and normalize BNDES CSV columns.

        The BNDES CSV uses semicolon-separated values with columns like:
        cliente, cnpj, subsetor_cnae_codigo, subsetor_cnae_nome,
        valor_contratado_reais, valor_desembolsado_reais, etc.

        We filter for telecom records where subsetor_cnae_codigo starts
        with "61" or subsetor_cnae_nome contains "telecomunic".
        """
        if raw_data.empty:
            return pd.DataFrame()

        # Identify columns (BNDES CSVs use varying column names)
        cols = {c.upper().strip(): c for c in raw_data.columns}

        cnpj_col = None
        for candidate in [
            "CNPJ", "CNPJ_CPFCLIENTEOPERACAO", "CNPJ_CPF",
            "CNPJ_CLIENTE", "CPF_CNPJ",
        ]:
            if candidate.upper() in cols:
                cnpj_col = cols[candidate.upper()]
                break

        name_col = None
        for candidate in [
            "CLIENTE", "NOME_CLIENTE", "RAZAO_SOCIAL",
            "CLIENTEOPERACAO", "NOME",
        ]:
            if candidate.upper() in cols:
                name_col = cols[candidate.upper()]
                break

        cnae_col = None
        for candidate in [
            "SUBSETOR_CNAE_CODIGO", "CNAE_SUBCLASSE", "SUBCLASSE_CNAE",
            "CNAE", "CNAESUBCLASSE", "SETOR_CNAE",
        ]:
            if candidate.upper() in cols:
                cnae_col = cols[candidate.upper()]
                break

        cnae_desc_col = None
        for candidate in [
            "SUBSETOR_CNAE_NOME", "DESCRICAO_CNAE", "NATUREZA_OPERACAO",
            "SUBSETOR_CNAE", "DESC_CNAE", "SETOR",
        ]:
            if candidate.upper() in cols:
                cnae_desc_col = cols[candidate.upper()]
                break

        value_col = None
        for candidate in [
            "VALOR_CONTRATADO_REAIS", "VALOR_CONTRATADO",
            "VALOR_DA_OPERACAO", "VALOR_OPERACAO", "VALOR",
            "VL_CONTRATADO",
        ]:
            if candidate.upper() in cols:
                value_col = cols[candidate.upper()]
                break

        disbursed_col = None
        for candidate in [
            "VALOR_DESEMBOLSADO_REAIS", "VALOR_DESEMBOLSADO",
            "DESEMBOLSOS", "VL_DESEMBOLSADO", "VALOR_DESEMBOLSO",
        ]:
            if candidate.upper() in cols:
                disbursed_col = cols[candidate.upper()]
                break

        rate_col = None
        for candidate in [
            "JUROS", "TAXA_JUROS", "CUSTO_FINANCEIRO", "TAXA",
            "JUROS_ANUAL",
        ]:
            if candidate.upper() in cols:
                rate_col = cols[candidate.upper()]
                break

        term_col = None
        for candidate in [
            "PRAZO_AMORTIZACAO_MESES", "PRAZO_CARENCIA_MESES",
            "PRAZO_MESES", "PRAZO_CARENCIA_AMORTIZACAO", "PRAZO",
            "PRAZO_AMORTIZACAO",
        ]:
            if candidate.upper() in cols:
                term_col = cols[candidate.upper()]
                break

        mun_col = None
        for candidate in [
            "MUNICIPIO_CODIGO", "MUNICIPIO_IBGE",
            "CODIGO_MUNICIPIO_IBGE", "COD_MUNICIPIO", "COD_IBGE",
        ]:
            if candidate.upper() in cols:
                mun_col = cols[candidate.upper()]
                break

        date_col = None
        for candidate in [
            "DATA_DA_CONTRATACAO", "DATA_CONTRATO", "DT_CONTRATACAO",
            "DATA_OPERACAO", "DATA",
        ]:
            if candidate.upper() in cols:
                date_col = cols[candidate.upper()]
                break

        if not cnpj_col:
            logger.warning(
                f"Could not identify CNPJ column. "
                f"Columns: {list(raw_data.columns)}"
            )
            return pd.DataFrame()

        # Build lookup tables
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT code, id FROM admin_level_2 WHERE country_code = 'BR'"
        )
        code_to_l2 = {code: l2_id for code, l2_id in cur.fetchall()}
        cur.execute(
            "SELECT national_id, id FROM providers WHERE country_code = 'BR'"
        )
        cnpj_to_provider = {nid: pid for nid, pid in cur.fetchall()}
        cur.close()
        conn.close()

        rows = []
        for _, record in raw_data.iterrows():
            # Filter for telecom sector:
            # subsetor_cnae_codigo starts with "61" OR
            # subsetor_cnae_nome contains "telecomunic"
            is_telecom = False

            if cnae_col:
                cnae = str(record.get(cnae_col, "")).strip()
                if cnae.startswith(TELECOM_CNAE_PREFIX):
                    is_telecom = True

            if not is_telecom and cnae_desc_col:
                cnae_desc = str(record.get(cnae_desc_col, "")).strip().lower()
                if "telecomunic" in cnae_desc:
                    is_telecom = True

            if not is_telecom:
                continue

            # Extract CNPJ
            cnpj = str(record.get(cnpj_col, "")).strip()
            if not cnpj or cnpj == "nan":
                continue

            # Borrower name
            name = str(record.get(name_col, "")).strip() if name_col else ""

            # Map CNPJ to provider_id
            provider_id = cnpj_to_provider.get(cnpj)

            # Sector description
            sector = ""
            if cnae_desc_col:
                sector = str(record.get(cnae_desc_col, "")).strip()
            if not sector or sector == "nan":
                sector = "Telecomunicações"

            # Contract value
            contract_value = 0
            if value_col:
                try:
                    val_str = (
                        str(record.get(value_col, "0"))
                        .replace(",", ".")
                        .replace(" ", "")
                    )
                    contract_value = float(val_str)
                except (ValueError, TypeError):
                    pass

            # Disbursed value
            disbursed = 0
            if disbursed_col:
                try:
                    dis_str = (
                        str(record.get(disbursed_col, "0"))
                        .replace(",", ".")
                        .replace(" ", "")
                    )
                    disbursed = float(dis_str)
                except (ValueError, TypeError):
                    pass

            # Interest rate
            interest_rate = None
            if rate_col:
                try:
                    rate_str = (
                        str(record.get(rate_col, ""))
                        .replace(",", ".")
                        .replace("%", "")
                        .replace(" ", "")
                    )
                    if rate_str and rate_str != "nan":
                        interest_rate = float(rate_str)
                except (ValueError, TypeError):
                    pass

            # Term in months
            term_months = None
            if term_col:
                try:
                    term_str = str(record.get(term_col, "")).strip()
                    if term_str and term_str != "nan":
                        term_months = int(float(term_str))
                except (ValueError, TypeError):
                    pass

            # Municipality code and l2_id
            mun_code = ""
            if mun_col:
                mun_code = str(record.get(mun_col, "")).strip()
                if mun_code and len(mun_code) > 7:
                    mun_code = mun_code[:7]
            l2_id = code_to_l2.get(mun_code) if mun_code else None

            # Contract date
            contract_date = None
            if date_col:
                date_raw = str(record.get(date_col, "")).strip()
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        contract_date = datetime.strptime(
                            date_raw[:10], fmt
                        ).date()
                        break
                    except (ValueError, TypeError):
                        continue

            rows.append({
                "borrower_cnpj": cnpj[:20],
                "borrower_name": (
                    name[:300] if name and name != "nan" else None
                ),
                "provider_id": provider_id,
                "sector": sector[:50] if sector else None,
                "contract_value_brl": contract_value,
                "disbursed_brl": disbursed,
                "interest_rate": interest_rate,
                "term_months": term_months,
                "municipality_code": mun_code[:10] if mun_code else None,
                "l2_id": l2_id,
                "contract_date": contract_date,
                "source": "bndes",
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} BNDES telecom loan records")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Upsert BNDES telecom loans into the database."""
        if data.empty:
            logger.warning("No BNDES loan data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        # Ensure table exists (check_for_updates may be skipped with force=True)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bndes_loans (
                id SERIAL PRIMARY KEY,
                borrower_cnpj VARCHAR(20),
                borrower_name VARCHAR(300),
                provider_id INTEGER REFERENCES providers(id),
                sector VARCHAR(50),
                contract_value_brl NUMERIC,
                disbursed_brl NUMERIC,
                interest_rate NUMERIC,
                term_months INTEGER,
                municipality_code VARCHAR(10),
                l2_id INTEGER REFERENCES admin_level_2(id),
                contract_date DATE,
                source VARCHAR(50),
                UNIQUE(borrower_cnpj, contract_date)
            )
        """)
        conn.commit()

        loaded = 0
        for _, row in data.iterrows():
            try:
                cur.execute("""
                    INSERT INTO bndes_loans
                    (borrower_cnpj, borrower_name, provider_id, sector,
                     contract_value_brl, disbursed_brl, interest_rate,
                     term_months, municipality_code, l2_id, contract_date, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (borrower_cnpj, contract_date) DO UPDATE SET
                        borrower_name = EXCLUDED.borrower_name,
                        provider_id = EXCLUDED.provider_id,
                        contract_value_brl = EXCLUDED.contract_value_brl,
                        disbursed_brl = EXCLUDED.disbursed_brl,
                        interest_rate = EXCLUDED.interest_rate,
                        term_months = EXCLUDED.term_months,
                        l2_id = EXCLUDED.l2_id
                """, (
                    row["borrower_cnpj"],
                    row["borrower_name"],
                    int(row["provider_id"]) if pd.notna(row.get("provider_id")) else None,
                    row["sector"],
                    row["contract_value_brl"],
                    row["disbursed_brl"],
                    row["interest_rate"],
                    int(row["term_months"]) if pd.notna(row.get("term_months")) else None,
                    row["municipality_code"],
                    int(row["l2_id"]) if pd.notna(row.get("l2_id")) else None,
                    row["contract_date"],
                    row["source"],
                ))
                loaded += 1
            except Exception as e:
                logger.debug(f"Skipping BNDES loan row: {e}")
                conn.rollback()

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} BNDES telecom loan records")

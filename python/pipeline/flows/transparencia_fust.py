"""Portal da Transparencia FUST/FUNTTEL spending pipeline.

Source: Portal da Transparencia API (Controladoria-Geral da Uniao)
URL: https://api.portaldatransparencia.gov.br/api-de-dados/despesas/por-orgao
Auth: chave-api-dados header (env TRANSPARENCIA_API_KEY)
Format: REST JSON

FUST (Fundo de Universalização dos Serviços de Telecomunicações) and
FUNTTEL (Fundo para o Desenvolvimento Tecnológico das Telecomunicações)
are the two main Brazilian federal funds for telecom development.

Tracking their spending reveals where the federal government is investing
in telecom infrastructure, which municipalities are receiving funds,
and what creditors (often ISPs) are being contracted.

Org codes:
  - 41232: FUST
  - 41903: FUNTTEL

Schedule: Weekly (Sunday 04:30 UTC)
Requires: TRANSPARENCIA_API_KEY environment variable (register at
          https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email)
"""
import logging
import os
from datetime import datetime

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

TRANSPARENCIA_BASE_URL = (
    "https://api.portaldatransparencia.gov.br/api-de-dados/despesas/por-orgao"
)

# FUST and FUNTTEL organ codes in SIAFI
FUST_ORG_CODE = "41232"
FUNTTEL_ORG_CODE = "41903"

ORG_NAMES = {
    FUST_ORG_CODE: "FUST - Fundo de Universalização dos Serviços de Telecomunicações",
    FUNTTEL_ORG_CODE: "FUNTTEL - Fundo para o Desenvolvimento Tecnológico das Telecomunicações",
}


class TransparenciaFUSTPipeline(BasePipeline):
    """Ingest FUST and FUNTTEL spending data from Portal da Transparencia.

    Fetches federal expenditure data for the two main Brazilian telecom funds,
    including committed and paid values per creditor (supplier). Maps creditor
    CNPJs to known ISP providers where possible.

    Requires TRANSPARENCIA_API_KEY environment variable for API authentication.
    Will fail with clear error if the key is not set or the API is unavailable.
    """

    def __init__(self):
        super().__init__("transparencia_fust")
        self._api_key = os.getenv("TRANSPARENCIA_API_KEY", "")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fust_spending (
                id SERIAL PRIMARY KEY,
                year INTEGER,
                month INTEGER,
                org_code VARCHAR(10),
                org_name VARCHAR(200),
                program_code VARCHAR(20),
                action_code VARCHAR(20),
                value_committed_brl NUMERIC,
                value_paid_brl NUMERIC,
                creditor_cnpj VARCHAR(20),
                creditor_name VARCHAR(300),
                state_code VARCHAR(2),
                source VARCHAR(50),
                UNIQUE(year, month, org_code, creditor_cnpj)
            )
        """)
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM fust_spending")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 50

    def download(self) -> list[dict]:
        """Fetch FUST and FUNTTEL expenditure from Portal da Transparencia API."""
        if not self._api_key:
            raise RuntimeError(
                "TRANSPARENCIA_API_KEY environment variable not set. "
                "Register at https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email "
                "to obtain a free API key, then set TRANSPARENCIA_API_KEY in your environment."
            )

        with PipelineHTTPClient(timeout=120) as http:
            all_records = []
            current_year = datetime.utcnow().year

            for org_code in [FUST_ORG_CODE, FUNTTEL_ORG_CODE]:
                org_name = ORG_NAMES[org_code]
                for year in range(2020, current_year + 1):
                    try:
                        records = self._fetch_org_year(
                            http, org_code, org_name, year
                        )
                        all_records.extend(records)
                        logger.info(
                            f"Org {org_code} year {year}: "
                            f"fetched {len(records)} records"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Transparencia API failed for org {org_code} "
                            f"year {year}: {e}"
                        )

            if not all_records:
                raise RuntimeError(
                    "Portal da Transparencia API returned no data for FUST/FUNTTEL. "
                    "Verify your API key is valid and the service is available."
                )

            logger.info(f"Total FUST/FUNTTEL records fetched: {len(all_records)}")
            return all_records

    def _fetch_org_year(
        self,
        http: PipelineHTTPClient,
        org_code: str,
        org_name: str,
        year: int,
    ) -> list[dict]:
        """Fetch expenditure records for a single org and year."""
        records = []
        page = 1
        max_pages = 50

        while page <= max_pages:
            headers = {"chave-api-dados": self._api_key}
            params = {
                "codigoOrgao": org_code,
                "ano": year,
                "pagina": page,
            }

            resp = http._retry_request(
                "GET", TRANSPARENCIA_BASE_URL,
                params=params, headers=headers,
            )
            data = resp.json()

            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("data", data.get("resultado", []))
                if not isinstance(items, list):
                    items = []

            if not items:
                break

            for item in items:
                records.append({
                    "year": year,
                    "org_code": org_code,
                    "org_name": org_name,
                    **item,
                })

            if len(items) < 100:
                break

            page += 1

        return records

    def validate_raw(self, data: list[dict]) -> None:
        if not data:
            raise ValueError("No FUST/FUNTTEL spending data returned")
        logger.info(f"Validating {len(data)} FUST/FUNTTEL spending records")

    def transform(self, raw_data: list[dict]) -> pd.DataFrame:
        """Normalize Portal da Transparencia responses into fust_spending schema."""
        rows = []
        for record in raw_data:
            year = record.get("year")
            if not year:
                year_raw = record.get("ano", record.get("exercicio", ""))
                try:
                    year = int(str(year_raw)[:4])
                except (ValueError, TypeError):
                    continue

            month = record.get("month")
            if not month:
                month_raw = record.get("mes", record.get("mesReferencia", ""))
                try:
                    month = int(str(month_raw)[:2])
                except (ValueError, TypeError):
                    month = 1

            org_code = str(
                record.get("org_code", "") or record.get("codigoOrgao", "")
            ).strip()

            org_name = str(
                record.get("org_name", "") or record.get("nomeOrgao", "")
            ).strip()

            program_code = str(
                record.get("codigoPrograma", "")
                or record.get("programa", {}).get("codigo", "")
                if isinstance(record.get("programa"), dict)
                else record.get("codigoPrograma", "")
            ).strip()

            action_code = str(
                record.get("codigoAcao", "")
                or record.get("acao", {}).get("codigo", "")
                if isinstance(record.get("acao"), dict)
                else record.get("codigoAcao", "")
            ).strip()

            committed_raw = record.get(
                "valorEmpenhado",
                record.get("valor_empenhado", record.get("empenhado", 0)),
            )
            try:
                committed = float(str(committed_raw).replace(",", ".").replace(" ", ""))
            except (ValueError, TypeError):
                committed = 0

            paid_raw = record.get(
                "valorPago",
                record.get("valor_pago", record.get("pago", 0)),
            )
            try:
                paid = float(str(paid_raw).replace(",", ".").replace(" ", ""))
            except (ValueError, TypeError):
                paid = 0

            creditor_cnpj = str(
                record.get("cnpjCredor", "")
                or record.get("cnpj_credor", "")
                or record.get("documentoCredor", "")
            ).strip()

            creditor_name = str(
                record.get("nomeCredor", "")
                or record.get("nome_credor", "")
                or record.get("razaoSocialCredor", "")
            ).strip()

            state_code = str(
                record.get("uf", "") or record.get("siglaUf", "")
            ).strip()[:2]

            rows.append({
                "year": year,
                "month": month,
                "org_code": org_code[:10] if org_code else None,
                "org_name": org_name[:200] if org_name else None,
                "program_code": program_code[:20] if program_code else None,
                "action_code": action_code[:20] if action_code else None,
                "value_committed_brl": committed,
                "value_paid_brl": paid,
                "creditor_cnpj": creditor_cnpj[:20] if creditor_cnpj else None,
                "creditor_name": creditor_name[:300] if creditor_name else None,
                "state_code": state_code or None,
                "source": "transparencia",
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} FUST/FUNTTEL spending records")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        if data.empty:
            logger.warning("No FUST/FUNTTEL spending data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        loaded = 0
        for _, row in data.iterrows():
            try:
                cur.execute("""
                    INSERT INTO fust_spending
                    (year, month, org_code, org_name, program_code, action_code,
                     value_committed_brl, value_paid_brl, creditor_cnpj,
                     creditor_name, state_code, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (year, month, org_code, creditor_cnpj) DO UPDATE SET
                        value_committed_brl = EXCLUDED.value_committed_brl,
                        value_paid_brl = EXCLUDED.value_paid_brl,
                        creditor_name = EXCLUDED.creditor_name,
                        program_code = EXCLUDED.program_code,
                        action_code = EXCLUDED.action_code
                """, (
                    row["year"],
                    row["month"],
                    row["org_code"],
                    row["org_name"],
                    row["program_code"],
                    row["action_code"],
                    row["value_committed_brl"],
                    row["value_paid_brl"],
                    row["creditor_cnpj"],
                    row["creditor_name"],
                    row["state_code"],
                    row["source"],
                ))
                loaded += 1
            except Exception as e:
                logger.debug(f"Skipping FUST spending row: {e}")
                conn.rollback()

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} FUST/FUNTTEL spending records")

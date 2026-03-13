"""DOU (Diario Oficial da Uniao) ANATEL Acts Pipeline.

Source: Querido Diário API (for municipal + state gazettes mentioning ANATEL/telecom)
        + PNCP API (for government procurement acts)
Format: REST JSON

Regulatory acts affecting ISPs — spectrum auctions, regulatory changes,
fines, license revocations, infrastructure permits. We aggregate from
multiple real government transparency APIs.

Note: The DOU itself (in.gov.br) blocks programmatic access.
We use Querido Diário (confirmed working at api.queridodiario.ok.org.br)
and PNCP as real alternative sources for regulatory intelligence.
"""
import logging
from datetime import datetime, timedelta

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

TELECOM_KEYWORDS = [
    "ANATEL", "telecomunicação", "telecomunicações", "espectro",
    "radiofrequência", "banda larga", "fibra óptica", "SCM",
    "SMP", "STFC", "antena", "torre", "estação rádio base",
]

# Querido Diário API (confirmed working)
QD_API_BASE = "https://api.queridodiario.ok.org.br/api/gazettes"

# PNCP API (confirmed working)
PNCP_API_BASE = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"


class DOUAnatelPipeline(BasePipeline):
    """Ingest telecom regulatory acts from government gazette APIs."""

    def __init__(self):
        super().__init__("dou_anatel")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS regulatory_acts (
                id SERIAL PRIMARY KEY,
                dou_section VARCHAR(20),
                published_date DATE,
                act_type VARCHAR(100),
                title TEXT,
                content_summary TEXT,
                keywords TEXT[],
                affects_providers TEXT[],
                source_url VARCHAR(500),
                source VARCHAR(50) DEFAULT 'gazette_api',
                UNIQUE (published_date, title)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_regulatory_acts_date ON regulatory_acts(published_date)")
        conn.commit()

        cur.execute("""
            SELECT COUNT(*) FROM regulatory_acts
            WHERE published_date >= CURRENT_DATE - INTERVAL '30 days'
        """)
        recent = cur.fetchone()[0]
        cur.close()
        conn.close()
        return recent < 5

    def download(self) -> list[dict]:
        """Download telecom regulatory acts from real government APIs."""
        all_records = []

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        with PipelineHTTPClient(timeout=60) as http:
            # Source 1: Querido Diário API — gazette mentions of ANATEL/telecom
            search_terms = ["ANATEL", "telecomunicacao regulamento", "espectro radiofrequencia"]
            for term in search_terms:
                try:
                    data = http.get_json(
                        QD_API_BASE,
                        params={
                            "querystring": term,
                            "since": start_date,
                            "until": end_date,
                            "size": 50,
                        },
                    )
                    gazettes = data.get("gazettes", []) if isinstance(data, dict) else []
                    for g in gazettes:
                        excerpts = g.get("excerpts", [])
                        excerpt = excerpts[0][:2000] if excerpts else ""
                        all_records.append({
                            "dou_section": "Gazette",
                            "published_date": str(g.get("date", ""))[:10],
                            "act_type": "Publicação em Diário Oficial",
                            "title": f"[{g.get('territory_name', 'Unknown')}] {term}: {excerpt[:200]}",
                            "content_summary": excerpt,
                            "keywords": [term, "ANATEL"],
                            "affects_providers": [],
                            "source_url": g.get("url", ""),
                            "source": "querido_diario",
                        })
                    logger.info(f"QD search '{term}': {len(gazettes)} results")
                except Exception as e:
                    logger.warning(f"Querido Diário search '{term}' failed: {e}")

            # Source 2: PNCP API — regulatory procurement acts (licitações)
            pncp_keywords = ["anatel", "telecomunicacao regulamento"]
            for keyword in pncp_keywords:
                try:
                    start_fmt = start_date.replace("-", "")[:8]
                    end_fmt = end_date.replace("-", "")[:8]
                    data = http.get_json(
                        PNCP_API_BASE,
                        params={
                            "dataInicial": start_fmt,
                            "dataFinal": end_fmt,
                            "q": keyword,
                            "pagina": 1,
                        },
                    )
                    items = data.get("data", []) if isinstance(data, dict) else []
                    for item in items[:50]:
                        org = item.get("orgaoEntidade", {})
                        unidade = item.get("unidadeOrgao", {})
                        pub_date = str(item.get("dataPublicacaoPncp", ""))[:10]
                        obj = item.get("objetoCompra", "")
                        all_records.append({
                            "dou_section": f"PNCP-{item.get('modalidadeNome', 'Licitação')}",
                            "published_date": pub_date,
                            "act_type": item.get("modalidadeNome", "Contratação"),
                            "title": f"[{org.get('razaoSocial', '')}] {obj[:300]}",
                            "content_summary": f"Órgão: {org.get('razaoSocial', '')}. "
                                               f"UF: {unidade.get('ufSigla', '')}. "
                                               f"Município: {unidade.get('municipioNome', '')}. "
                                               f"Objeto: {obj}. "
                                               f"Valor: R$ {item.get('valorTotalEstimado', 0):,.2f}",
                            "keywords": [keyword, "PNCP", "licitação"],
                            "affects_providers": [],
                            "source_url": item.get("linkSistemaOrigem", ""),
                            "source": "pncp",
                        })
                    logger.info(f"PNCP search '{keyword}': {len(items)} results")
                except Exception as e:
                    logger.warning(f"PNCP search '{keyword}' failed: {e}")

        if not all_records:
            raise RuntimeError(
                "No regulatory act data from any source (Querido Diário, PNCP). "
                "Both APIs may be temporarily unavailable."
            )

        logger.info(f"Total regulatory act records: {len(all_records)}")
        return all_records

    def validate_raw(self, data) -> None:
        if not data:
            raise ValueError("No regulatory act data")
        logger.info(f"Validating {len(data)} regulatory act records")

    def transform(self, raw_data) -> pd.DataFrame:
        if not raw_data:
            return pd.DataFrame()

        # Data is already in the right format from download()
        rows = []
        for record in raw_data:
            pub_date = record.get("published_date", "")
            if not pub_date or len(pub_date) < 8:
                continue

            title = str(record.get("title", ""))[:500]
            if not title:
                continue

            rows.append({
                "dou_section": str(record.get("dou_section", ""))[:20],
                "published_date": pub_date[:10],
                "act_type": str(record.get("act_type", ""))[:100],
                "title": title,
                "content_summary": str(record.get("content_summary", ""))[:2000],
                "keywords": record.get("keywords", ["ANATEL"]),
                "affects_providers": record.get("affects_providers", []),
                "source_url": str(record.get("source_url", ""))[:500],
                "source": record.get("source", "gazette_api"),
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} regulatory act records")
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
                pub_date = row.get("published_date")
                if isinstance(pub_date, str):
                    pub_date = pub_date[:10]

                keywords = row.get("keywords", [])
                if isinstance(keywords, str):
                    keywords = [keywords]

                affects = row.get("affects_providers", [])
                if isinstance(affects, str):
                    affects = [affects]

                cur.execute("""
                    INSERT INTO regulatory_acts
                        (dou_section, published_date, act_type, title,
                         content_summary, keywords, affects_providers, source_url, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (published_date, title) DO NOTHING
                """, (
                    str(row.get("dou_section", "")),
                    pub_date,
                    str(row.get("act_type", "")),
                    str(row.get("title", ""))[:500],
                    str(row.get("content_summary", ""))[:2000],
                    keywords,
                    affects,
                    str(row.get("source_url", ""))[:500],
                    str(row.get("source", "gazette_api")),
                ))
                loaded += 1
                cur.execute("RELEASE SAVEPOINT row_sp")
            except Exception as e:
                logger.warning(f"Failed to load regulatory act: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT row_sp")

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} regulatory act records")

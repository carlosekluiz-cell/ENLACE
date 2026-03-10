"""Anatel broadband subscriber data pipeline — HIGHEST PRIORITY.

Source: Anatel open data on dados.gov.br (CKAN)
Dataset: "acessos---banda-larga-fixa"
Format: CSV (semicolon-delimited, ISO-8859-1 encoding)
Key columns: Ano, Mes, Grupo Economico, Empresa, CNPJ, UF, Municipio,
             Codigo IBGE, Tecnologia, Meio de Acesso, Acessos
Update: Monthly (~45 days after month end)

Downloads the full CSV (millions of rows), maps CNPJ -> provider_id,
Codigo IBGE -> l2_id, Tecnologia -> normalized tech, and loads into
broadband_subscribers. Auto-creates providers for unknown CNPJs.
"""
import logging
from datetime import datetime

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import TECHNOLOGY_MAP, DataSourceURLs
from python.pipeline.http_client import PipelineHTTPClient
from python.pipeline.loaders.postgres_loader import refresh_materialized_view, upsert_batch
from python.pipeline.transformers.provider_normalizer import normalize_provider_name

logger = logging.getLogger(__name__)

TECH_MAP = {
    "Fibra Optica": "fiber",
    "Fibra Óptica": "fiber",
    "Cabo Coaxial / HFC": "cable",
    "Cabo Coaxial/HFC": "cable",
    "xDSL": "dsl",
    "Radio": "wireless",
    "Rádio": "wireless",
    "Satelite": "satellite",
    "Satélite": "satellite",
    "Outras": "other",
}
TECH_MAP.update(TECHNOLOGY_MAP)


class AnatelBroadbandPipeline(BasePipeline):
    """Ingest real Anatel monthly broadband subscriber data."""

    def __init__(self):
        super().__init__("anatel_broadband")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT MAX(year_month) FROM broadband_subscribers")
        latest = cur.fetchone()[0]
        cur.close()
        conn.close()
        if not latest:
            return True
        now = datetime.utcnow()
        expected = f"{now.year}-{now.month - 2:02d}" if now.month > 2 else f"{now.year - 1}-{now.month + 10:02d}"
        return latest < expected

    def download(self) -> pd.DataFrame:
        """Download broadband subscriber CSV. Tries direct Anatel ZIP first, falls back to CKAN."""
        now = datetime.utcnow()
        with PipelineHTTPClient(timeout=600) as http:
            # Try direct ZIP download first (dados.gov.br CKAN is blocked by AWS WAF)
            # The broadband ZIP contains per-year CSVs; extract only recent years
            try:
                logger.info(f"Downloading broadband ZIP from {self.urls.anatel_broadband_zip}")
                year_filters = [str(now.year), str(now.year - 1)]
                df = http.get_csvs_from_zip(
                    self.urls.anatel_broadband_zip, sep=";", encoding="iso-8859-1",
                    csv_name_filters=year_filters,
                )
                logger.info(f"Downloaded {len(df)} broadband records from direct ZIP (years: {year_filters})")
                return df
            except Exception as e:
                logger.warning(f"Direct ZIP download failed: {e}, trying CKAN fallback...")

            # Fallback to CKAN
            logger.info("Resolving Anatel broadband CKAN resource URL...")
            csv_url = http.resolve_ckan_resource_url(
                self.urls.anatel_broadband_dataset,
                resource_format="CSV",
                ckan_base=self.urls.anatel_ckan_base,
            )
            logger.info(f"Downloading broadband CSV from {csv_url}")
            df = http.get_csv(csv_url, sep=";", encoding="iso-8859-1")
            logger.info(f"Downloaded {len(df)} broadband records")

        return df

    def validate_raw(self, data: pd.DataFrame) -> None:
        if data.empty:
            raise ValueError("Empty broadband CSV")
        logger.info(f"Broadband CSV columns: {list(data.columns)}")
        # Check for essential columns
        cols_lower = [c.lower().strip() for c in data.columns]
        has_ibge = any("ibge" in c or "codigo" in c for c in cols_lower)
        has_acessos = any("acesso" in c for c in cols_lower)
        if not has_ibge:
            raise ValueError("No IBGE code column found")
        if not has_acessos:
            raise ValueError("No Acessos column found")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Map CSV columns to database schema."""
        df = raw_data.copy()
        df.columns = [c.strip() for c in df.columns]

        # Find column names (they vary between releases)
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if "codigo" in cl and "ibge" in cl:
                col_map["ibge_code"] = c
            elif "ibge" in cl and "codigo" not in cl:
                col_map.setdefault("ibge_code", c)
            elif cl == "ano":
                col_map["ano"] = c
            elif cl in ("mes", "mês"):
                col_map["mes"] = c
            elif "cnpj" in cl:
                col_map["cnpj"] = c
            elif "tecnologia" in cl:
                col_map["tecnologia"] = c
            elif "acesso" in cl:
                col_map["acessos"] = c
            elif "empresa" in cl:
                col_map["empresa"] = c

        # Build lookup tables from DB
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT code, id FROM admin_level_2 WHERE country_code = 'BR'")
        code_to_l2 = {code: l2_id for code, l2_id in cur.fetchall()}
        cur.execute("SELECT national_id, id FROM providers WHERE country_code = 'BR'")
        cnpj_to_provider = {nid: pid for nid, pid in cur.fetchall()}
        cur.close()
        conn.close()

        rows = []
        auto_created_providers = {}

        for _, row in df.iterrows():
            # Map IBGE code to l2_id
            ibge_code = str(row.get(col_map.get("ibge_code", ""), "")).strip()
            l2_id = code_to_l2.get(ibge_code)
            if l2_id is None:
                continue

            # Map CNPJ to provider_id
            cnpj = str(row.get(col_map.get("cnpj", ""), "")).strip()
            provider_id = cnpj_to_provider.get(cnpj)
            if provider_id is None and cnpj and cnpj != "nan":
                # Auto-create provider if not seen before
                if cnpj not in auto_created_providers:
                    empresa = str(row.get(col_map.get("empresa", ""), "")).strip()
                    provider_id = self._auto_create_provider(cnpj, empresa)
                    auto_created_providers[cnpj] = provider_id
                    cnpj_to_provider[cnpj] = provider_id
                else:
                    provider_id = auto_created_providers[cnpj]

            if provider_id is None:
                continue

            # Map technology
            tech_raw = str(row.get(col_map.get("tecnologia", ""), "")).strip()
            technology = TECH_MAP.get(tech_raw, tech_raw.lower() if tech_raw else "other")

            # Build year_month
            ano = str(row.get(col_map.get("ano", ""), "")).strip()
            mes = str(row.get(col_map.get("mes", ""), "")).strip()
            try:
                year_month = f"{int(ano)}-{int(mes):02d}"
            except (ValueError, TypeError):
                continue

            # Parse subscriber count (may have dot thousands separator)
            acessos_raw = str(row.get(col_map.get("acessos", ""), "")).strip()
            try:
                subscribers = int(acessos_raw.replace(".", "").replace(",", ""))
            except (ValueError, TypeError):
                continue

            if subscribers <= 0:
                continue

            rows.append({
                "l2_id": l2_id,
                "provider_id": provider_id,
                "year_month": year_month,
                "technology": technology,
                "subscribers": subscribers,
            })

        if auto_created_providers:
            logger.info(f"Auto-created {len(auto_created_providers)} new providers")

        result = pd.DataFrame(rows)
        # Aggregate duplicates (same l2, provider, month, tech)
        if not result.empty:
            result = result.groupby(
                ["l2_id", "provider_id", "year_month", "technology"], as_index=False
            )["subscribers"].sum()

        self.rows_processed = len(result)
        return result

    def _auto_create_provider(self, cnpj: str, name: str) -> int:
        """Create a new provider record for an unknown CNPJ. Returns provider ID."""
        conn = self._get_connection()
        cur = conn.cursor()
        name_normalized = normalize_provider_name(name) if name and name != "nan" else cnpj
        cur.execute("""
            INSERT INTO providers (national_id, name, name_normalized, classification, status, country_code)
            VALUES (%s, %s, %s, 'PPP', 'active', 'BR')
            ON CONFLICT (national_id) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """, (cnpj, name or cnpj, name_normalized))
        provider_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return provider_id

    def load(self, data: pd.DataFrame) -> None:
        """Load broadband subscriber records."""
        if data.empty:
            logger.warning("No broadband data to load")
            return

        # Delete existing records for the year_months we're loading
        conn = self._get_connection()
        cur = conn.cursor()
        months = data["year_month"].unique().tolist()
        cur.execute(
            "DELETE FROM broadband_subscribers WHERE year_month = ANY(%s)",
            (months,)
        )
        conn.commit()
        cur.close()
        conn.close()

        columns = ["l2_id", "provider_id", "year_month", "technology", "subscribers"]
        values = [tuple(row) for row in data[columns].values]

        inserted, updated = upsert_batch(
            table="broadband_subscribers",
            columns=columns,
            values=values,
            conflict_columns=["id"],
            db_config=self.db_config,
        )
        self.rows_inserted = inserted
        self.rows_updated = updated
        logger.info(f"Loaded {inserted} broadband subscriber records")

    def post_load(self) -> None:
        """Recompute competitive analysis and refresh materialized views."""
        self._compute_competitive_analysis()
        try:
            refresh_materialized_view("mv_market_summary", concurrently=True, db_config=self.db_config)
            logger.info("Refreshed mv_market_summary")
        except Exception as e:
            logger.warning(f"Could not refresh mv_market_summary: {e}")

    def _compute_competitive_analysis(self):
        """Compute HHI and market share data per municipality per month."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT l2_id, year_month, provider_id, SUM(subscribers) as total_subs
            FROM broadband_subscribers
            GROUP BY l2_id, year_month, provider_id
        """)
        rows = cur.fetchall()

        market_data = {}
        for l2_id, ym, prov_id, subs in rows:
            key = (l2_id, ym)
            if key not in market_data:
                market_data[key] = []
            market_data[key].append((prov_id, subs))

        import json
        now = datetime.utcnow()
        values = []
        for (l2_id, ym), entries in market_data.items():
            total = sum(s for _, s in entries)
            if total == 0:
                continue
            shares = [(pid, s / total) for pid, s in entries]
            hhi = sum(share ** 2 for _, share in shares) * 10000
            leader_pid, leader_share = max(shares, key=lambda x: x[1])
            details = json.dumps([
                {"provider_id": pid, "market_share": round(share, 4), "subscribers": s}
                for (pid, s), (_, share) in zip(entries, shares)
            ])
            if hhi > 5000:
                threat = "high"
            elif hhi > 2500:
                threat = "medium"
            else:
                threat = "low"
            values.append((
                l2_id, ym, now, round(hhi, 2), leader_pid,
                round(leader_share, 4), details, "stable", threat
            ))

        if values:
            months = list(set(ym for _, ym in market_data.keys()))
            cur.execute("DELETE FROM competitive_analysis WHERE year_month = ANY(%s)", (months,))

            from psycopg2.extras import execute_values
            execute_values(cur, """
                INSERT INTO competitive_analysis
                (l2_id, year_month, computed_at, hhi_index, leader_provider_id,
                 leader_market_share, provider_details, growth_trend, threat_level)
                VALUES %s
            """, values, page_size=1000)
            conn.commit()
            logger.info(f"Computed competitive analysis for {len(values)} market segments")

        cur.close()
        conn.close()

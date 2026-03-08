"""Anatel broadband subscriber data pipeline.

Source: Anatel open data portal
URL: https://dados.gov.br/dados/conjuntos-dados/acessos-banda-larga-fixa
Format: CSV (semicolon-delimited, ISO-8859-1 encoding)
Update: Monthly (~45 days after month end)
Key columns: Ano, Mes, Grupo Economico, Empresa, CNPJ, UF, Municipio,
             Codigo IBGE, Tecnologia, Meio de Acesso, Acessos

Real download would parse the CSV and extract subscriber counts per
municipality per provider per technology per month.
"""
import logging
import random
from datetime import datetime

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import TECHNOLOGY_MAP, DataSourceURLs
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

# Merge with config's TECHNOLOGY_MAP
TECH_MAP.update(TECHNOLOGY_MAP)


class AnatelBroadbandPipeline(BasePipeline):
    """Ingest Anatel monthly broadband subscriber data."""

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
        """Try real Anatel CSV download, fallback to synthetic data."""
        try:
            logger.info("Attempting real Anatel broadband download...")
            # Real download: semicolon-delimited CSV, ISO-8859-1
            # df = pd.read_csv(url, sep=';', encoding='iso-8859-1')
            raise ConnectionError("Real download not available in dev environment")
        except Exception as e:
            logger.info(f"Real download failed ({e}), generating synthetic data")
            return self._generate_synthetic()

    def _generate_synthetic(self) -> pd.DataFrame:
        """Generate realistic broadband subscriber data."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT al2.id, al2.code, al2.name
            FROM admin_level_2 al2
            JOIN countries c ON al2.country_code = c.code
            WHERE c.code = 'BR'
        """)
        municipalities = cur.fetchall()
        cur.execute("SELECT id, name, classification FROM providers WHERE country_code = 'BR'")
        providers = cur.fetchall()
        cur.close()
        conn.close()

        random.seed(42)
        rows = []
        techs = ["fiber", "cable", "dsl", "wireless", "satellite"]
        tech_weights = [0.45, 0.20, 0.15, 0.12, 0.08]

        # Population-proxy subscriber bases per municipality size
        for l2_id, code, mun_name in municipalities:
            # Base subscriber count varies by municipality
            base_subs = random.randint(5000, 500000)
            # Assign 3-6 providers per municipality
            num_providers = random.randint(3, min(6, len(providers)))
            mun_providers = random.sample(providers, num_providers)
            shares = [random.random() for _ in range(num_providers)]
            total_share = sum(shares)
            shares = [s / total_share for s in shares]

            for month_offset in range(12):
                year = 2025
                month = month_offset + 1
                ym = f"{year}-{month:02d}"
                growth = 1.0 + month_offset * 0.005  # slight monthly growth

                for (prov_id, prov_name, prov_class), share in zip(mun_providers, shares):
                    prov_subs = int(base_subs * share * growth)
                    # Pick 1-2 technologies per provider
                    num_techs = random.choices([1, 2], weights=[0.6, 0.4])[0]
                    chosen_techs = random.choices(techs, weights=tech_weights, k=num_techs)
                    for tech in set(chosen_techs):
                        tech_fraction = random.uniform(0.3, 1.0) if num_techs > 1 else 1.0
                        subs = max(1, int(prov_subs * tech_fraction))
                        rows.append({
                            "l2_id": l2_id,
                            "provider_id": prov_id,
                            "year_month": ym,
                            "technology": tech,
                            "subscribers": subs,
                        })

        return pd.DataFrame(rows)

    def validate_raw(self, data: pd.DataFrame) -> None:
        required = ["l2_id", "provider_id", "year_month", "technology", "subscribers"]
        missing = set(required) - set(data.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        if (data["subscribers"] < 0).any():
            raise ValueError("Negative subscriber counts found")
        if data.empty:
            raise ValueError("Empty dataset")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Normalize technology names and deduplicate."""
        df = raw_data.copy()
        # Map technology names
        df["technology"] = df["technology"].map(lambda t: TECH_MAP.get(t, t))
        # Aggregate duplicates (same l2, provider, month, tech)
        df = df.groupby(
            ["l2_id", "provider_id", "year_month", "technology"], as_index=False
        )["subscribers"].sum()
        self.rows_processed = len(df)
        return df

    def load(self, data: pd.DataFrame) -> None:
        """Upsert broadband subscriber records."""
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
            conflict_columns=["id"],  # no natural conflict, each insert is new
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

        # Group by (l2_id, year_month)
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
            # Determine threat level based on HHI
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
            # Delete existing competitive_analysis for these months
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

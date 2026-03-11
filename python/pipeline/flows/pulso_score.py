"""Pulso Score batch computation pipeline.

Computes composite ISP health scores for ALL providers with broadband
subscriber data, stores results in ``pulso_scores``, and assigns ranks.

Lifecycle:
    1. check_for_updates — always returns True (scores should be recomputed regularly)
    2. download — fetches list of active provider IDs from broadband_subscribers
    3. transform — computes sub-scores for each provider (in batches)
    4. load — persists scores, preserves previous_score, computes rank
    5. post_load — updates rank column based on composite score ordering
"""

import logging
import math
from datetime import datetime
from typing import Any

import pandas as pd

from python.pipeline.base import BasePipeline

logger = logging.getLogger(__name__)

# Weight configuration (must match python/api/services/pulso_score.py)
WEIGHTS = {
    "growth": 0.20,
    "fiber": 0.15,
    "quality": 0.15,
    "compliance": 0.15,
    "financial": 0.15,
    "market": 0.10,
    "bndes": 0.10,
}

TIER_MAP = [
    (90, "S"),
    (75, "A"),
    (60, "B"),
    (40, "C"),
    (0, "D"),
]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _score_to_tier(score: float) -> str:
    for threshold, tier in TIER_MAP:
        if score >= threshold:
            return tier
    return "D"


class PulsoScorePipeline(BasePipeline):
    """Batch Pulso Score computation for all ISP providers."""

    def __init__(self):
        super().__init__("pulso_score")

    def check_for_updates(self) -> bool:
        """Always run — scores should be refreshed periodically."""
        return True

    def download(self) -> list[int]:
        """Get all provider IDs that have broadband subscriber data."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT provider_id
            FROM broadband_subscribers
            WHERE provider_id IS NOT NULL
            ORDER BY provider_id
        """)
        provider_ids = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        logger.info(f"Found {len(provider_ids)} providers with broadband data")
        self.rows_processed = len(provider_ids)
        return provider_ids

    def validate_raw(self, data: Any) -> None:
        if not data:
            raise ValueError("No providers found with broadband data")
        logger.info(f"Will compute scores for {len(data)} providers")

    def transform(self, raw_data: list[int]) -> pd.DataFrame:
        """Compute all sub-scores for each provider using sync DB queries."""
        conn = self._get_connection()
        cur = conn.cursor()

        # Pre-fetch bulk data for efficiency
        logger.info("Pre-fetching subscriber data...")
        subscriber_data = self._fetch_subscriber_data(cur)
        logger.info("Pre-fetching quality data...")
        quality_data = self._fetch_quality_data(cur)
        logger.info("Pre-fetching compliance data...")
        compliance_data = self._fetch_compliance_data(cur)
        logger.info("Pre-fetching BNDES data...")
        bndes_data = self._fetch_bndes_data(cur)
        logger.info("Pre-fetching previous scores...")
        previous_scores = self._fetch_previous_scores(cur)

        scores = []
        batch_size = 500
        for i in range(0, len(raw_data), batch_size):
            batch = raw_data[i:i + batch_size]
            for provider_id in batch:
                try:
                    score = self._compute_single(
                        provider_id,
                        subscriber_data,
                        quality_data,
                        compliance_data,
                        bndes_data,
                        previous_scores,
                    )
                    scores.append(score)
                except Exception as e:
                    logger.warning(f"Failed to score provider {provider_id}: {e}")

            logger.info(f"Scored {min(i + batch_size, len(raw_data))}/{len(raw_data)} providers")

        cur.close()
        conn.close()

        logger.info(f"Computed scores for {len(scores)} providers")
        return pd.DataFrame(scores)

    def _fetch_subscriber_data(self, cur) -> dict:
        """Pre-fetch all subscriber data grouped by provider."""
        # Latest month per provider
        cur.execute("""
            SELECT provider_id, MAX(year_month) AS latest_ym
            FROM broadband_subscribers
            GROUP BY provider_id
        """)
        latest_months = {row[0]: row[1].strip() for row in cur.fetchall()}

        # Latest month subscriber totals (all techs + fiber only)
        cur.execute("""
            SELECT
                bs.provider_id,
                bs.year_month,
                SUM(bs.subscribers) AS total,
                SUM(CASE WHEN LOWER(bs.technology) = 'fiber' THEN bs.subscribers ELSE 0 END) AS fiber
            FROM broadband_subscribers bs
            GROUP BY bs.provider_id, bs.year_month
            ORDER BY bs.provider_id, bs.year_month DESC
        """)
        monthly = {}
        for row in cur.fetchall():
            pid = row[0]
            ym = row[1].strip()
            if pid not in monthly:
                monthly[pid] = []
            monthly[pid].append({
                "year_month": ym,
                "total": int(row[2]),
                "fiber": int(row[3]),
            })

        # Market totals per municipality for latest month
        cur.execute("""
            WITH latest AS (
                SELECT l2_id, MAX(year_month) AS ym
                FROM broadband_subscribers
                GROUP BY l2_id
            )
            SELECT bs.l2_id, bs.provider_id, SUM(bs.subscribers) AS subs
            FROM broadband_subscribers bs
            JOIN latest l ON bs.l2_id = l.l2_id AND bs.year_month = l.ym
            GROUP BY bs.l2_id, bs.provider_id
        """)
        market_shares: dict[int, list] = {}
        market_totals: dict[int, int] = {}
        for row in cur.fetchall():
            l2_id, pid, subs = row[0], row[1], int(row[2])
            if pid not in market_shares:
                market_shares[pid] = []
            market_shares[pid].append({"l2_id": l2_id, "subs": subs})
            market_totals[l2_id] = market_totals.get(l2_id, 0) + subs

        return {
            "latest_months": latest_months,
            "monthly": monthly,
            "market_shares": market_shares,
            "market_totals": market_totals,
        }

    def _fetch_quality_data(self, cur) -> dict[int, float]:
        """Pre-fetch average quality indicator values per provider's municipalities."""
        # Provider-level quality
        cur.execute("""
            SELECT provider_id, AVG(value) AS avg_val
            FROM quality_indicators
            WHERE provider_id IS NOT NULL
              AND metric_type IN (
                  'broadband_penetration_pct', 'fiber_penetration_pct',
                  'technology_diversity', 'yoy_growth_pct'
              )
            GROUP BY provider_id
        """)
        direct = {row[0]: float(row[1]) for row in cur.fetchall()}

        # Municipality-level quality for all providers
        cur.execute("""
            SELECT bs.provider_id, AVG(qi.value) AS avg_val
            FROM quality_indicators qi
            JOIN (
                SELECT DISTINCT provider_id, l2_id
                FROM broadband_subscribers
            ) bs ON qi.l2_id = bs.l2_id
            WHERE qi.metric_type IN (
                'broadband_penetration_pct', 'fiber_penetration_pct',
                'technology_diversity'
            )
            GROUP BY bs.provider_id
        """)
        indirect = {row[0]: float(row[1]) for row in cur.fetchall()}

        # Merge: prefer direct, fall back to indirect
        result = {}
        for pid in set(list(direct.keys()) + list(indirect.keys())):
            if pid in direct:
                result[pid] = direct[pid]
            else:
                result[pid] = indirect[pid]
        return result

    def _fetch_compliance_data(self, cur) -> dict[int, dict]:
        """Pre-fetch compliance-relevant data per provider."""
        # Provider status and services
        cur.execute("""
            SELECT id, status, services, classification
            FROM providers
        """)
        providers_info = {}
        for row in cur.fetchall():
            providers_info[row[0]] = {
                "status": row[1],
                "services": row[2],
                "classification": row[3],
            }

        # Spectrum license counts
        cur.execute("""
            SELECT provider_id, COUNT(*) AS cnt
            FROM spectrum_licenses
            WHERE provider_id IS NOT NULL
            GROUP BY provider_id
        """)
        spectrum = {row[0]: int(row[1]) for row in cur.fetchall()}

        # Quality seal counts
        try:
            cur.execute("""
                SELECT provider_id, COUNT(*) AS cnt
                FROM quality_seals
                WHERE provider_id IS NOT NULL
                GROUP BY provider_id
            """)
            seals = {row[0]: int(row[1]) for row in cur.fetchall()}
        except Exception:
            seals = {}

        return {
            "providers_info": providers_info,
            "spectrum": spectrum,
            "seals": seals,
        }

    def _fetch_bndes_data(self, cur) -> dict:
        """Pre-fetch BNDES loan data."""
        # Direct provider loans
        cur.execute("""
            SELECT provider_id, COUNT(*) AS cnt, COALESCE(SUM(contract_value_brl), 0) AS total
            FROM bndes_loans
            WHERE provider_id IS NOT NULL
            GROUP BY provider_id
        """)
        direct = {row[0]: {"cnt": int(row[1]), "total": float(row[2])} for row in cur.fetchall()}

        # Municipality-level BNDES telecom loans
        cur.execute("""
            SELECT l2_id, COUNT(*) AS cnt
            FROM bndes_loans
            WHERE sector ILIKE '%%telecom%%'
            GROUP BY l2_id
        """)
        muni_loans = {row[0]: int(row[1]) for row in cur.fetchall()}

        return {"direct": direct, "muni_loans": muni_loans}

    def _fetch_previous_scores(self, cur) -> dict[int, float]:
        """Fetch the most recent score per provider."""
        cur.execute("""
            SELECT DISTINCT ON (provider_id) provider_id, score
            FROM pulso_scores
            ORDER BY provider_id, computed_at DESC
        """)
        return {row[0]: float(row[1]) for row in cur.fetchall()}

    def _compute_single(
        self,
        provider_id: int,
        sub_data: dict,
        quality_data: dict[int, float],
        compliance_data: dict,
        bndes_data: dict,
        previous_scores: dict[int, float],
    ) -> dict:
        """Compute all sub-scores for a single provider from pre-fetched data."""

        # --- Growth score ---
        monthly = sub_data["monthly"].get(provider_id, [])
        growth_score = self._calc_growth(monthly)

        # --- Fiber score ---
        fiber_score = self._calc_fiber(monthly)

        # --- Quality score ---
        quality_score = _clamp(min(quality_data.get(provider_id, 30.0), 100.0))

        # --- Compliance score ---
        compliance_score = self._calc_compliance(provider_id, compliance_data)

        # --- Financial score ---
        financial_score = self._calc_financial(monthly)

        # --- Market score ---
        market_score = self._calc_market(provider_id, sub_data)

        # --- BNDES score ---
        bndes_score = self._calc_bndes(provider_id, sub_data, bndes_data)

        # --- Composite ---
        composite = (
            growth_score * WEIGHTS["growth"]
            + fiber_score * WEIGHTS["fiber"]
            + quality_score * WEIGHTS["quality"]
            + compliance_score * WEIGHTS["compliance"]
            + financial_score * WEIGHTS["financial"]
            + market_score * WEIGHTS["market"]
            + bndes_score * WEIGHTS["bndes"]
        )
        composite = round(_clamp(composite), 2)
        tier = _score_to_tier(composite)

        prev = previous_scores.get(provider_id)
        change = round(composite - prev, 2) if prev is not None else None

        return {
            "provider_id": provider_id,
            "score": composite,
            "growth_score": round(growth_score, 2),
            "fiber_score": round(fiber_score, 2),
            "quality_score": round(quality_score, 2),
            "compliance_score": round(compliance_score, 2),
            "financial_score": round(financial_score, 2),
            "market_score": round(market_score, 2),
            "bndes_score": round(bndes_score, 2),
            "tier": tier,
            "previous_score": prev,
            "score_change": change,
        }

    def _calc_growth(self, monthly: list[dict]) -> float:
        """Growth from subscriber YoY comparison."""
        if len(monthly) < 2:
            return 40.0

        latest = monthly[0]
        latest_ym = latest["year_month"]
        # Find 12 months prior
        try:
            year = int(latest_ym[:4]) - 1
            month = latest_ym[5:]
            target_ym = f"{year}-{month}"
        except (ValueError, IndexError):
            return 40.0

        prior = None
        for m in monthly:
            if m["year_month"] <= target_ym:
                prior = m
                break

        if not prior or prior["total"] <= 0:
            return 40.0

        growth_rate = (latest["total"] - prior["total"]) / prior["total"]

        if growth_rate < -0.20:
            return 0.0
        elif growth_rate < 0:
            return _clamp(30.0 * (1.0 + growth_rate / 0.20))
        elif growth_rate < 0.20:
            return _clamp(30.0 + 60.0 * (growth_rate / 0.20))
        else:
            return _clamp(90.0 + 10.0 * min(growth_rate - 0.20, 0.30) / 0.30)

    def _calc_fiber(self, monthly: list[dict]) -> float:
        """Fiber share of total subscribers in latest month."""
        if not monthly:
            return 0.0
        latest = monthly[0]
        if latest["total"] <= 0:
            return 0.0
        return _clamp(latest["fiber"] / latest["total"] * 100.0)

    def _calc_compliance(self, provider_id: int, data: dict) -> float:
        """Compliance from status, spectrum, seals, and services."""
        score = 0.0
        info = data["providers_info"].get(provider_id, {})

        if info.get("status") and info["status"].lower() == "active":
            score += 30.0

        services = info.get("services")
        if services:
            if isinstance(services, list):
                svc_count = len(services)
            elif isinstance(services, dict):
                svc_count = len(services)
            else:
                svc_count = 0
            score += min(svc_count * 5.0, 20.0)

        if data["spectrum"].get(provider_id, 0) > 0:
            score += 30.0

        if data["seals"].get(provider_id, 0) > 0:
            score += 20.0

        return _clamp(score)

    def _calc_financial(self, monthly: list[dict]) -> float:
        """Financial stability from subscriber trend variance."""
        if len(monthly) < 2:
            return 20.0

        totals = [m["total"] for m in monthly[:12] if m["total"] > 0]
        if not totals:
            return 0.0

        mean = sum(totals) / len(totals)
        if mean <= 0:
            return 0.0

        variance = sum((t - mean) ** 2 for t in totals) / len(totals)
        std_dev = variance ** 0.5
        cv = std_dev / mean

        stability = _clamp(90.0 - cv * 160.0, 10.0, 90.0)
        scale_bonus = min(10.0, max(0.0, math.log10(max(mean, 1)) - 1.0) * 3.33)

        return _clamp(stability + scale_bonus)

    def _calc_market(self, provider_id: int, sub_data: dict) -> float:
        """Market share and geographic reach."""
        shares = sub_data["market_shares"].get(provider_id, [])
        if not shares:
            return 0.0

        market_totals = sub_data["market_totals"]
        share_values = []
        for entry in shares:
            mkt = market_totals.get(entry["l2_id"], 0)
            if mkt > 0:
                share_values.append(entry["subs"] / mkt)

        if not share_values:
            return 0.0

        avg_share = sum(share_values) / len(share_values)
        muni_count = len(share_values)

        share_score = avg_share * 100.0
        reach_bonus = min(30.0, math.log10(max(muni_count, 1)) * 15.0)

        return _clamp(share_score * 0.7 + reach_bonus)

    def _calc_bndes(self, provider_id: int, sub_data: dict, bndes_data: dict) -> float:
        """BNDES loan access score."""
        direct = bndes_data["direct"].get(provider_id)
        if direct and direct["cnt"] > 0:
            total = direct["total"]
            amount_bonus = min(40.0, math.log10(max(total, 1)) / 8.0 * 40.0)
            return _clamp(60.0 + amount_bonus)

        # Indirect: check municipalities
        shares = sub_data["market_shares"].get(provider_id, [])
        muni_loans = bndes_data["muni_loans"]
        loan_count = sum(muni_loans.get(s["l2_id"], 0) for s in shares)

        if loan_count > 0:
            return _clamp(min(50.0, 20.0 + loan_count * 5.0))

        return 15.0

    def load(self, data: pd.DataFrame) -> None:
        """Persist scores to pulso_scores table."""
        if data.empty:
            logger.warning("No scores to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        loaded = 0
        for _, row in data.iterrows():
            cur.execute("""
                INSERT INTO pulso_scores (
                    provider_id, score, growth_score, fiber_score, quality_score,
                    compliance_score, financial_score, market_score, bndes_score,
                    tier, previous_score, score_change, computed_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
            """, (
                int(row["provider_id"]),
                float(row["score"]),
                float(row["growth_score"]),
                float(row["fiber_score"]),
                float(row["quality_score"]),
                float(row["compliance_score"]),
                float(row["financial_score"]),
                float(row["market_score"]),
                float(row["bndes_score"]),
                str(row["tier"]),
                float(row["previous_score"]) if row["previous_score"] is not None else None,
                float(row["score_change"]) if row["score_change"] is not None else None,
            ))
            loaded += 1

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} Pulso Scores")

    def post_load(self) -> None:
        """Update rank column based on composite score ordering."""
        conn = self._get_connection()
        cur = conn.cursor()

        # Assign ranks based on latest score per provider
        cur.execute("""
            WITH latest_scores AS (
                SELECT DISTINCT ON (provider_id)
                    id, provider_id, score
                FROM pulso_scores
                ORDER BY provider_id, computed_at DESC
            ),
            ranked AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY score DESC) AS rnk
                FROM latest_scores
            )
            UPDATE pulso_scores ps
            SET rank = r.rnk
            FROM ranked r
            WHERE ps.id = r.id
        """)

        conn.commit()
        updated = cur.rowcount
        cur.close()
        conn.close()
        logger.info(f"Updated ranks for {updated} providers")

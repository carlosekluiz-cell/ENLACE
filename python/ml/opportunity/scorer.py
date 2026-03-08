"""XGBoost opportunity scoring with SHAP explanations.

Scores municipalities for ISP expansion opportunity using a trained
XGBoost classifier, with SHAP values providing interpretable feature
importance for each prediction.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import psycopg2
import shap
from sklearn.model_selection import StratifiedKFold, cross_val_score
from xgboost import XGBClassifier

from python.ml.config import (
    DB_CONFIG,
    DEMAND_WEIGHT,
    COMPETITION_WEIGHT,
    GROWTH_WEIGHT,
    INFRASTRUCTURE_WEIGHT,
    MODEL_VERSION,
    XGBOOST_PARAMS,
)
from python.ml.opportunity.demand_model import compute_demand_score
from python.ml.opportunity.features import ALL_FEATURE_NAMES, FeatureExtractor

logger = logging.getLogger(__name__)


class OpportunityScorer:
    """Score municipalities for expansion opportunity using XGBoost + SHAP.

    The scorer combines:
    1. An XGBoost classifier trained on synthetic historical entry patterns
       to predict whether ISP expansion would succeed.
    2. Sub-scores for demand, competition, infrastructure, and growth that
       provide interpretable components of the overall opportunity.
    3. SHAP values for feature-level explanations of each score.
    """

    def __init__(self):
        self.model: Optional[XGBClassifier] = None
        self.feature_names: list[str] = list(ALL_FEATURE_NAMES)
        self.explainer: Optional[shap.TreeExplainer] = None
        self._train_auc: Optional[float] = None

    def train(self, features_df: pd.DataFrame, labels: pd.Series) -> dict:
        """Train XGBoost model with cross-validation.

        Args:
            features_df: DataFrame with feature columns for each municipality.
            labels: Binary labels (1 = successful entry, 0 = unsuccessful).

        Returns:
            Dictionary with training metrics (auc, accuracy, cv_scores).
        """
        # Ensure we only use the defined feature columns
        X = features_df[self.feature_names].copy()
        y = labels.copy()

        logger.info(
            "Training XGBoost on %d samples with %d features",
            len(X),
            len(self.feature_names),
        )

        # Initialize model — adjust params for small datasets
        params = dict(XGBOOST_PARAMS)
        if len(X) < 100:
            params["min_child_weight"] = 1
            params["n_estimators"] = 100
            params["max_depth"] = 4
        self.model = XGBClassifier(**params)

        # Cross-validation with stratification
        n_folds = min(5, min(y.sum(), (1 - y).sum()))
        n_folds = max(2, int(n_folds))
        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
        cv_scores = cross_val_score(
            self.model, X, y, cv=cv, scoring="roc_auc"
        )
        logger.info(
            "Cross-validation AUC: %.4f (+/- %.4f)",
            cv_scores.mean(),
            cv_scores.std(),
        )

        # Train on full data
        self.model.fit(X, y)

        # Create SHAP explainer
        self.explainer = shap.TreeExplainer(self.model)

        self._train_auc = float(cv_scores.mean())

        metrics = {
            "auc": float(cv_scores.mean()),
            "auc_std": float(cv_scores.std()),
            "cv_scores": cv_scores.tolist(),
            "n_samples": len(X),
            "n_features": len(self.feature_names),
        }
        logger.info("Training complete. AUC=%.4f", metrics["auc"])
        return metrics

    def score(self, features: dict) -> dict:
        """Score a single municipality for expansion opportunity.

        Args:
            features: Dictionary mapping feature names to values.

        Returns:
            Dictionary compatible with OpportunityScoreResponse:
                - composite_score: Overall opportunity score (0-100)
                - confidence: Model confidence (0-1)
                - demand_score: Demand sub-score (0-100)
                - competition_score: Competition sub-score (0-100)
                - infrastructure_score: Infrastructure sub-score (0-100)
                - growth_score: Growth sub-score (0-100)
                - top_factors: List of top SHAP-based factors
                - features: Raw feature values
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        # Prepare feature vector
        x = np.array(
            [[features.get(f, 0.0) for f in self.feature_names]], dtype=np.float64
        )
        x_df = pd.DataFrame(x, columns=self.feature_names)

        # Predict probability
        prob = float(self.model.predict_proba(x_df)[0, 1])

        # SHAP values for explainability
        shap_values = self.explainer.shap_values(x_df)
        if isinstance(shap_values, list):
            # For binary classification, take the positive class
            sv = shap_values[1][0] if len(shap_values) > 1 else shap_values[0][0]
        else:
            sv = shap_values[0]

        # Top factors: sort by absolute SHAP value
        factor_importance = sorted(
            zip(self.feature_names, sv),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        top_factors = [
            {
                "feature": name,
                "importance": round(float(val), 4),
                "direction": "positive" if val > 0 else "negative",
            }
            for name, val in factor_importance[:5]
        ]

        # Compute sub-scores
        demand_score = self._compute_demand_subscore(features)
        competition_score = self._compute_competition_subscore(features)
        infrastructure_score = self._compute_infrastructure_subscore(features)
        growth_score = self._compute_growth_subscore(features)

        # Composite score: weighted combination of sub-scores,
        # adjusted by model probability
        weighted_sub = (
            demand_score * DEMAND_WEIGHT
            + competition_score * COMPETITION_WEIGHT
            + infrastructure_score * INFRASTRUCTURE_WEIGHT
            + growth_score * GROWTH_WEIGHT
        )

        # Blend sub-score approach with ML probability
        composite = 0.5 * weighted_sub + 0.5 * (prob * 100)
        composite = max(0.0, min(100.0, composite))

        return {
            "composite_score": round(composite, 2),
            "confidence": round(prob, 4),
            "demand_score": round(demand_score, 2),
            "competition_score": round(competition_score, 2),
            "infrastructure_score": round(infrastructure_score, 2),
            "growth_score": round(growth_score, 2),
            "top_factors": top_factors,
            "features": {k: round(float(v), 4) if isinstance(v, (int, float, np.floating, np.integer)) else v for k, v in features.items()},
        }

    def score_all(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Score all municipalities and return results DataFrame.

        Args:
            features_df: DataFrame from FeatureExtractor.extract_all_features().

        Returns:
            DataFrame with scores for each municipality.
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        results = []
        for _, row in features_df.iterrows():
            features = row.to_dict()
            municipality_id = int(features.pop("municipality_id", 0))
            score_result = self.score(features)
            score_result["municipality_id"] = municipality_id
            results.append(score_result)

        return pd.DataFrame(results)

    def save_scores_to_db(
        self, scores_df: pd.DataFrame, conn=None
    ) -> int:
        """Store computed scores in the opportunity_scores table.

        Args:
            scores_df: DataFrame from score_all() with municipality_id.
            conn: Optional database connection.

        Returns:
            Number of rows inserted.
        """
        own_conn = conn is None
        if own_conn:
            conn = psycopg2.connect(**DB_CONFIG)

        try:
            # Get municipality metadata
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, code, country_code, ST_X(centroid) AS lon,
                           ST_Y(centroid) AS lat
                    FROM admin_level_2
                    WHERE centroid IS NOT NULL
                    """
                )
                muni_meta = {
                    row[0]: {
                        "code": row[1],
                        "country_code": row[2].strip() if row[2] else "BR",
                        "lon": row[3],
                        "lat": row[4],
                    }
                    for row in cur.fetchall()
                }

            now = datetime.now(timezone.utc)
            insert_count = 0

            with conn.cursor() as cur:
                # Clear existing scores for this model version
                cur.execute(
                    "DELETE FROM opportunity_scores WHERE model_version = %s",
                    (MODEL_VERSION,),
                )

                for _, row in scores_df.iterrows():
                    mid = int(row["municipality_id"])
                    meta = muni_meta.get(mid)
                    if not meta:
                        continue

                    # Build features JSON (exclude non-feature columns)
                    features_json = {}
                    if "features" in row and isinstance(row["features"], dict):
                        features_json = row["features"]
                    if "top_factors" in row:
                        features_json["top_factors"] = row["top_factors"]

                    cur.execute(
                        """
                        INSERT INTO opportunity_scores (
                            country_code, geographic_type, geographic_id,
                            centroid, computed_at,
                            demand_score, competition_score,
                            infrastructure_score, growth_score,
                            composite_score, confidence,
                            features, model_version
                        ) VALUES (
                            %s, 'municipality', %s,
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s,
                            %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            meta["country_code"],
                            meta["code"],
                            meta["lon"],
                            meta["lat"],
                            now,
                            float(row["demand_score"]),
                            float(row["competition_score"]),
                            float(row["infrastructure_score"]),
                            float(row["growth_score"]),
                            float(row["composite_score"]),
                            float(row["confidence"]),
                            json.dumps(features_json, default=str),
                            MODEL_VERSION,
                        ),
                    )
                    insert_count += 1

            conn.commit()
            logger.info("Saved %d opportunity scores to database", insert_count)
            return insert_count

        except Exception:
            conn.rollback()
            raise
        finally:
            if own_conn:
                conn.close()

    # ------------------------------------------------------------------
    # Sub-score computation
    # ------------------------------------------------------------------

    def _compute_demand_subscore(self, features: dict) -> float:
        """Compute demand sub-score (0-100)."""
        return compute_demand_score(features)

    def _compute_competition_subscore(self, features: dict) -> float:
        """Compute competition opportunity sub-score (0-100).

        Higher score = less competition = more opportunity.
        """
        hhi = features.get("hhi_index", 5000)
        provider_count = features.get("provider_count", 2)
        leader_share = features.get("leader_share", 0.5)
        tech_gap = features.get("technology_gap", 0)

        # Low provider count = more opportunity
        provider_score = max(0, 100 - provider_count * 20)

        # Moderate HHI is best for entry (not monopoly, not hyper-competitive)
        if hhi > 6000:
            # Near-monopoly: hard to enter
            hhi_score = max(0, 60 - (hhi - 6000) / 100)
        elif hhi > 3000:
            # Concentrated but not monopoly: good opportunity
            hhi_score = 80
        else:
            # Competitive market: harder to gain share
            hhi_score = max(20, hhi / 50)

        # Technology gap bonus: no fiber = massive opportunity
        tech_bonus = tech_gap * 30

        # High leader share = vulnerable to disruption
        leader_score = min(40, leader_share * 50)

        score = (
            provider_score * 0.25
            + hhi_score * 0.30
            + tech_bonus
            + leader_score * 0.15
        )
        return max(0.0, min(100.0, score))

    def _compute_infrastructure_subscore(self, features: dict) -> float:
        """Compute infrastructure readiness sub-score (0-100).

        Higher score = better infrastructure = easier/cheaper deployment.
        """
        road_density = features.get("road_density_km_per_km2", 0.1)
        power_coverage = features.get("power_line_coverage", 0)
        terrain_slope = features.get("avg_terrain_slope", 5)

        # Road density: more roads = easier to deploy fiber along ROW
        road_score = min(100, road_density * 50)

        # Power line coverage: existing utility poles = potential fiber routes
        power_score = power_coverage * 100

        # Terrain: flatter = cheaper construction
        slope_score = max(0, 100 - terrain_slope * 5)

        return road_score * 0.40 + power_score * 0.35 + slope_score * 0.25

    def _compute_growth_subscore(self, features: dict) -> float:
        """Compute growth potential sub-score (0-100).

        Combines subscriber growth trends with demographic growth.
        """
        sub_growth_3m = features.get("subscriber_growth_3m", 0)
        sub_growth_12m = features.get("subscriber_growth_12m", 0)
        household_growth = features.get("household_growth_rate", 0.01)
        young_pop = features.get("young_population_pct", 0.25)

        # Subscriber growth: positive growth indicates expanding market
        growth_3m_score = min(50, max(0, sub_growth_3m * 500))
        growth_12m_score = min(50, max(0, sub_growth_12m * 200))

        # Household growth: growing population = growing demand
        hh_growth_score = min(30, max(0, household_growth * 2000))

        # Young population: higher digital adoption
        young_score = min(20, max(0, (young_pop - 0.15) * 200))

        return min(
            100.0,
            growth_3m_score + growth_12m_score + hh_growth_score + young_score,
        )

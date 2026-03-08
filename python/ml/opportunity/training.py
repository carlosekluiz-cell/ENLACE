"""Training pipeline for the opportunity scoring model.

Generates synthetic training labels from the data (since we don't have
historical expansion outcome data), trains the XGBoost model, evaluates
via cross-validation, and scores all municipalities.
"""

import logging

import numpy as np
import pandas as pd
import psycopg2

from python.ml.config import DB_CONFIG, MODEL_VERSION
from python.ml.opportunity.features import ALL_FEATURE_NAMES, FeatureExtractor
from python.ml.opportunity.scorer import OpportunityScorer

logger = logging.getLogger(__name__)


def generate_training_labels(features_df: pd.DataFrame) -> pd.Series:
    """Generate training labels from feature patterns.

    Since we have synthetic data, create training labels based on
    heuristics that capture what makes ISP entry successful:

    Success (label=1):
        - High income + low penetration (underserved affluent market)
        - Technology gap present (no fiber provider)
        - Strong population growth

    Failure (label=0):
        - Low income + high penetration (saturated low-margin market)
        - High competition (many providers, low HHI)
        - Declining or stagnant growth

    The labels are deterministic given the features, ensuring
    reproducibility.

    Args:
        features_df: DataFrame from FeatureExtractor.extract_all_features().

    Returns:
        Binary Series with 1=success, 0=failure.
    """
    df = features_df.copy()

    # Compute a composite heuristic score
    score = np.zeros(len(df))

    # Income effect: higher income = more likely to succeed
    income_norm = (df["avg_income_per_capita"] - df["avg_income_per_capita"].min()) / (
        df["avg_income_per_capita"].max() - df["avg_income_per_capita"].min() + 1e-9
    )
    score += income_norm * 2.0

    # Penetration gap: lower penetration = more opportunity
    penetration_gap = 1.0 - df["current_penetration"].clip(0, 1)
    score += penetration_gap * 2.0

    # Technology gap: no fiber = opportunity for fiber ISP
    score += df["technology_gap"] * 1.5

    # Growth: positive subscriber growth = expanding market
    score += df["subscriber_growth_12m"].clip(-0.5, 0.5) * 1.0

    # Household growth
    score += df["household_growth_rate"].clip(0, 0.05) * 20.0

    # Infrastructure: roads and power help
    score += df["road_density_km_per_km2"].clip(0, 5) * 0.3
    score += df["power_line_coverage"] * 0.5

    # Urbanization: urban areas are easier to serve
    score += df["urbanization_rate"] * 0.8

    # Provider count penalty: more providers = harder market
    score -= df["provider_count"] * 0.3

    # Convert to binary labels using median split with some noise
    # to avoid perfect separation
    rng = np.random.RandomState(42)
    noise = rng.normal(0, 0.3, len(score))
    score_noisy = score + noise

    median = np.median(score_noisy)
    labels = (score_noisy >= median).astype(int)

    logger.info(
        "Generated %d labels: %d positive (%.1f%%), %d negative (%.1f%%)",
        len(labels),
        labels.sum(),
        labels.mean() * 100,
        (1 - labels).sum(),
        (1 - labels.mean()) * 100,
    )

    return pd.Series(labels, index=features_df.index)


def train_and_evaluate() -> dict:
    """Full training pipeline: extract features, train, evaluate, save.

    Steps:
    1. Extract features for all municipalities.
    2. Generate synthetic training labels.
    3. Train XGBoost model with cross-validation.
    4. Score all municipalities.
    5. Save scores to the opportunity_scores table.

    Returns:
        Dictionary with training metrics and scoring results.
    """
    conn = psycopg2.connect(**DB_CONFIG)

    try:
        # Step 1: Extract features
        logger.info("Step 1: Extracting features...")
        extractor = FeatureExtractor(conn=conn)
        features_df = extractor.extract_all_features()
        logger.info("Features shape: %s", features_df.shape)

        if features_df.empty:
            logger.error("No features extracted. Check database connectivity.")
            return {"error": "No features extracted"}

        # Step 2: Generate training labels
        logger.info("Step 2: Generating training labels...")
        labels = generate_training_labels(features_df)

        # Step 3: Train model
        logger.info("Step 3: Training XGBoost model...")
        scorer = OpportunityScorer()

        # Prepare features-only DataFrame (exclude municipality_id)
        feature_cols = [c for c in ALL_FEATURE_NAMES if c in features_df.columns]
        X = features_df[feature_cols]

        metrics = scorer.train(X, labels)
        logger.info("Training metrics: %s", metrics)

        # Step 4: Score all municipalities
        logger.info("Step 4: Scoring all municipalities...")
        scores_df = scorer.score_all(features_df)
        logger.info(
            "Scored %d municipalities. Score range: %.1f - %.1f",
            len(scores_df),
            scores_df["composite_score"].min(),
            scores_df["composite_score"].max(),
        )

        # Step 5: Save to database
        logger.info("Step 5: Saving scores to database...")
        saved_count = scorer.save_scores_to_db(scores_df, conn=conn)

        # Summary statistics
        result = {
            "auc": metrics["auc"],
            "auc_std": metrics["auc_std"],
            "n_samples": metrics["n_samples"],
            "scored_count": saved_count,
            "model_version": MODEL_VERSION,
            "score_stats": {
                "mean": round(float(scores_df["composite_score"].mean()), 2),
                "std": round(float(scores_df["composite_score"].std()), 2),
                "min": round(float(scores_df["composite_score"].min()), 2),
                "max": round(float(scores_df["composite_score"].max()), 2),
                "median": round(float(scores_df["composite_score"].median()), 2),
            },
        }

        logger.info("Pipeline complete. Results: %s", result)
        return result

    finally:
        conn.close()

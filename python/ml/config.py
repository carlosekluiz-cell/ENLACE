"""ML model configuration and cost benchmarks."""

import os

# Database connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "enlace"),
    "user": os.getenv("DB_USER", "enlace"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# Model hyperparameters
XGBOOST_PARAMS = {
    "n_estimators": 200,
    "max_depth": 6,
    "learning_rate": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "random_state": 42,
}

# Feature weights for sub-scores
DEMAND_WEIGHT = 0.30
COMPETITION_WEIGHT = 0.25
INFRASTRUCTURE_WEIGHT = 0.20
GROWTH_WEIGHT = 0.25

# Brazilian broadband pricing for affordability calculations
MIN_BROADBAND_PRICE_BRL = 79.90  # Cheapest fiber plan
AFFORDABILITY_INCOME_RATIO = 1.5  # Household income must be > 1.5x price

# Model versioning
MODEL_VERSION = "xgb_v1.0"

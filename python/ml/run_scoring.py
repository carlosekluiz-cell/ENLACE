"""Run the full opportunity scoring pipeline.

Usage:
    cd /home/dev/enlace
    PYTHONPATH=. python python/ml/run_scoring.py
"""

import logging
import os
import sys

# Ensure project root is on the path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Suppress noisy library loggers
logging.getLogger("shap").setLevel(logging.WARNING)

from python.ml.opportunity.training import train_and_evaluate

if __name__ == "__main__":
    results = train_and_evaluate()

    if "error" in results:
        print(f"ERROR: {results['error']}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Opportunity Scoring Pipeline — Complete")
    print(f"{'='*60}")
    print(f"  Training AUC:        {results.get('auc', 'N/A'):.4f}")
    print(f"  AUC Std Dev:         {results.get('auc_std', 'N/A'):.4f}")
    print(f"  Municipalities scored: {results.get('scored_count', 0)}")
    print(f"  Model version:       {results.get('model_version', 'N/A')}")
    print(f"  Score stats:")
    stats = results.get("score_stats", {})
    print(f"    Mean:   {stats.get('mean', 0):.1f}")
    print(f"    Median: {stats.get('median', 0):.1f}")
    print(f"    Min:    {stats.get('min', 0):.1f}")
    print(f"    Max:    {stats.get('max', 0):.1f}")
    print(f"    Std:    {stats.get('std', 0):.1f}")
    print(f"{'='*60}")

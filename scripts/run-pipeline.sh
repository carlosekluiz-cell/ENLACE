#!/bin/bash
# Enlace Pipeline Runner
# Usage: ./run-pipeline.sh [--once|--telecom|--weather]
# Defaults to running the APScheduler daemon

set -e
cd /home/dev/enlace
export PYTHONPATH=/home/dev/enlace

case "${1:-daemon}" in
    --once)
        echo "[$(date)] Running all pipelines once..."
        python3 -m python.pipeline.scheduler --once
        ;;
    --telecom)
        echo "[$(date)] Running telecom pipelines only..."
        python3 -c "
from python.pipeline.scheduler import run_daily_telecom
run_daily_telecom()
"
        ;;
    --weather)
        echo "[$(date)] Running weather pipeline only..."
        python3 -c "
from python.pipeline.scheduler import run_daily_weather
run_daily_weather()
"
        ;;
    daemon|*)
        echo "[$(date)] Starting pipeline scheduler daemon..."
        python3 -m python.pipeline.scheduler
        ;;
esac

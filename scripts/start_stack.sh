#!/bin/bash
# (Re)start the RF propagation stack: Rust engine + FastAPI + frontend.
# Run from repo root:  bash scripts/start_stack.sh
# Logs land in ./logs/. Safe to re-run (kills by port, not by name —
# pkill -f with these names would match your own shell and kill it).

set -u
cd "$(dirname "$0")/.."
mkdir -p logs
set -a; source .env 2>/dev/null; set +a

pkill -x pulso-rf-engine 2>/dev/null
fuser -k 8897/tcp 2>/dev/null
sleep 1

SRTM_TILE_DIR=data/terrain/dtm DSM_TILE_DIR=data/terrain/dsm GROUND_TILE_DIR=data/terrain/ground \
  RF_ENGINE_ADDR=127.0.0.1:50051 \
  nohup ./rust/target/release/pulso-rf-engine >>logs/rf-engine.log 2>&1 &

TERRAIN_TILE_DIR=data/terrain \
  DEV_MODE=1 \
  CALIBRATION_UPLOAD_TOKEN="${CALIBRATION_UPLOAD_TOKEN:-}" \
  RF_ENGINE_TLS_CA= \
  CORS_ORIGINS='["http://localhost:3000","http://127.0.0.1:3901","http://localhost:3901"]' \
  nohup python3 -m uvicorn python.api.main:app --port 8897 >>logs/api.log 2>&1 &

# Frontend (optional; built with NEXT_PUBLIC_API_URL=http://127.0.0.1:8897)
if [ "${WITH_FRONTEND:-1}" = "1" ] && [ -d frontend/.next ]; then
  fuser -k 3901/tcp 2>/dev/null
  (cd frontend && PORT=3901 nohup npm start >>../logs/next.log 2>&1 &)
fi

sleep 6
echo "listening: $(ss -tln | grep -cE '50051|8897|3901')/3 (engine 50051, api 8897, frontend 3901)"

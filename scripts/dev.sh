#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then echo 'Run: python -m venv .venv && .venv/bin/pip install -r backend/requirements.txt'; exit 1; fi
if [ ! -d frontend/node_modules ]; then npm --prefix frontend install; fi
PYTHONPATH="$PWD/backend:$PWD" .venv/bin/uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8000 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
npm --prefix frontend run dev

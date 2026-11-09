#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
(uvicorn app.main:app --app-dir backend --reload --port 8000) &
(cd frontend && npm install && npm run dev)

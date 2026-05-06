#!/usr/bin/env bash
# Week 5 Day 1: quick smoke — DB init, unit tests, optional web import.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> init_db"
python src/init_db.py

echo "==> pytest"
python -m pytest tests/ -q

echo "==> import web_app"
python -c "import sys; sys.path.insert(0,'src'); import web_app; print('web_app OK')"

echo "Smoke complete."

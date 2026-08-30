#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
  echo ".venv not found. Run scripts/setup_pyenv_and_venv.sh first."
  exit 1
fi

.venv/bin/python -m pip install --upgrade pip setuptools wheel

if [ -f uv.lock ]; then
  .venv/bin/python scripts/generate_requirements.py
fi

if [ -f requirements-uv.txt ]; then
  .venv/bin/pip install -r requirements-uv.txt
fi

.venv/bin/pip install -e .
echo "Installed project requirements in .venv"

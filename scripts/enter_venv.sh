#!/usr/bin/env bash
if [ -f .venv/bin/activate ]; then
  echo "Activating .venv (run 'deactivate' to exit)..."
  # shellcheck disable=SC1091
  . .venv/bin/activate
else
  echo ".venv not found. Run scripts/setup_pyenv_and_venv.sh first."
  exit 1
fi

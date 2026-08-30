#!/usr/bin/env bash
set -euo pipefail

# Lightweight setup script: install pyenv if missing, install latest Python 3.13.x,
# create a virtualenv `.venv` and install pinned requirements from `uv.lock`.

PY_VERSION="${PY_VERSION:-3.13}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
export PATH="$PYENV_ROOT/bin:$PATH"

echo "Project root: $PROJECT_ROOT"
echo "Desired Python version prefix: $PY_VERSION"

if ! command -v pyenv >/dev/null 2>&1; then
  echo "pyenv not found; installing pyenv to $PYENV_ROOT (no sudo)..."
  curl https://pyenv.run | bash
  export PATH="$PYENV_ROOT/bin:$PATH"
fi

if command -v pyenv >/dev/null 2>&1; then
  eval "$(pyenv init --path)" || true
  eval "$(pyenv init -)" || true
fi

# update pyenv and python-build if present
if [ -d "$PYENV_ROOT" ]; then
  git -C "$PYENV_ROOT" pull --ff-only || true
  if [ -d "$PYENV_ROOT/plugins/python-build" ]; then
    git -C "$PYENV_ROOT/plugins/python-build" pull --ff-only || true
  fi
fi

echo "Finding latest ${PY_VERSION}.x from pyenv..."
LATEST=$($PYENV_ROOT/bin/pyenv install --list | sed -n 's/^ *//p' | grep -E "^${PY_VERSION}\\.[0-9]+" | tail -1 || true)
if [ -z "$LATEST" ]; then
  echo "No ${PY_VERSION} entries found in pyenv. Run 'pyenv update' or update python-build." >&2
  exit 1
fi
echo "Selected Python: $LATEST"

if ! $PYENV_ROOT/bin/pyenv versions --bare | grep -qx "$LATEST"; then
  echo "Installing $LATEST with pyenv (this may take several minutes)."
  set +e
  $PYENV_ROOT/bin/pyenv install "$LATEST"
  RC=$?
  set -e
  if [ $RC -ne 0 ]; then
    echo "pyenv install failed. Missing OS build dependencies are the most common cause."
    echo "On Debian/Ubuntu run:" 
    echo "  sudo apt update && sudo apt install -y build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev libgdbm-dev libnss3-dev ca-certificates"
    echo "On Fedora/RHEL install the equivalent development packages."
    exit 1
  fi
fi

$PYENV_ROOT/bin/pyenv local "$LATEST"
PYBIN="$PYENV_ROOT/versions/$LATEST/bin/python"
echo "Using python: $($PYBIN --version)"

echo "Creating virtualenv .venv with $PYBIN"
rm -rf .venv
$PYBIN -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel

if [ -f uv.lock ]; then
  echo "Generating requirements-uv.txt from uv.lock"
  .venv/bin/python scripts/generate_requirements.py
fi

if [ -f requirements-uv.txt ]; then
  echo "Installing pinned requirements from requirements-uv.txt"
  .venv/bin/pip install -r requirements-uv.txt
fi

echo "Installing project in editable mode"
.venv/bin/pip install -e . || true

echo ""
echo "Done. Activate the venv with:"
echo "  source .venv/bin/activate"
echo "Or run: .venv/bin/python -m pip <command>"

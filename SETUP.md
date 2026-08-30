# Setup (pyenv + Python 3.13, project venv)

These repository scripts will install a user-local `pyenv`, pick a recent Python `3.13.x`, create `.venv`, and install pinned requirements from `uv.lock`.

Usage (simple):

1. Make the scripts executable (optional) and run the setup script:

```bash
bash scripts/setup_pyenv_and_venv.sh
```

1. If `setup_pyenv_and_venv.sh` reports a missing system dependency during `pyenv install`, install the OS build packages (Debian/Ubuntu example):

```bash
sudo apt update
sudo apt install -y build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
  libsqlite3-dev libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev libgdbm-dev libnss3-dev ca-certificates
```

1. Install the project into the venv (re-runs requirements generation and installs editable package):

```bash
bash scripts/install_project.sh
```

1. Enter the venv interactively:

```bash
source .venv/bin/activate
# or
bash scripts/enter_venv.sh
```

Notes:

- The scripts use `pyenv` and avoid altering the system Python.
- By default the scripts pick the latest `3.13.x` available to `pyenv`. You can set `PY_VERSION=3.13` or override `PYENV_ROOT` in your environment.

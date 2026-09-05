#!/usr/bin/env bash
set -euo pipefail

# Python venv support is not always present on the base image.
if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3-venv
fi

if [ ! -d venv ]; then
  python3 -m venv venv
fi

./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

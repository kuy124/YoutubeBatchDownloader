#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv-linux
.venv-linux/bin/python -m pip install -r requirements.txt
echo 'Installed. Start with: bash run.sh'

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec .venv-linux/bin/python -m app.main "$@"

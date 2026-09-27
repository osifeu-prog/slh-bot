#!/bin/sh
set -eu

python -m pip install --no-cache-dir "uvicorn==0.35.0" >/tmp/slh-mcp-pip.log 2>&1
exec python -m uvicorn slh_mcp.server:app --host 0.0.0.0 --port "${PORT:-8080}"

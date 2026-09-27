#!/bin/sh
set -eu

python -m pip install --no-cache-dir "uvicorn==0.35.0" >/tmp/slh-mcp-pip.log 2>&1
python -c 'import uvicorn; print("SLH_MCP_UVICORN_READY", uvicorn.__version__)'
exec python -m uvicorn slh_mcp.server:app --host 0.0.0.0 --port "${PORT:-8080}"

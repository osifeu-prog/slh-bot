FROM python:3.11-slim

WORKDIR /app

COPY slh_mcp/requirements.txt /tmp/slh-mcp-requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
 && python -m pip install --no-cache-dir -r /tmp/slh-mcp-requirements.txt \
 && python -m uvicorn --version \
 && python -c "from importlib.metadata import version; import mcp, uvicorn; print('SLH_MCP_RUNTIME_DEPS_OK', version('mcp'), uvicorn.__version__)"

COPY . .

ENV PYTHONUNBUFFERED=1

COPY slh_mcp/boot.sh /usr/local/bin/slh-mcp-boot
RUN chmod +x /usr/local/bin/slh-mcp-boot
CMD ["/usr/local/bin/slh-mcp-boot"]
# Railway deployment trigger: startCommand is intentionally executed through sh for ${PORT:-8080} expansion.

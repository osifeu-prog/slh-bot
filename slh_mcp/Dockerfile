FROM python:3.11-slim

WORKDIR /app

COPY slh_mcp/requirements.txt /tmp/slh-mcp-requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
 && python -m pip install --no-cache-dir -r /tmp/slh-mcp-requirements.txt \
 && python -m uvicorn --version

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "exec python -m uvicorn slh_mcp.server:app --host 0.0.0.0 --port ${PORT:-8080}"]

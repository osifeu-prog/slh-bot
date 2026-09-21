FROM python:3.11-slim

WORKDIR /app

COPY slh_mcp/requirements.txt /tmp/slh-mcp-requirements.txt
RUN pip install --no-cache-dir -r /tmp/slh-mcp-requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "exec uvicorn slh_mcp.server:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]

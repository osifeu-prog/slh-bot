FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/state && chmod +x /app/start_railway.sh

# Railway build retry marker; no runtime behavior change.
CMD ["/app/start_railway.sh"]

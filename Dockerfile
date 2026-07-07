FROM python:3.11-slim
WORKDIR /app
COPY . /app/

# Create minimal config.json (token will come from env)
RUN echo '{"SUPER_ADMIN": 8789977826, "SITE_DIR": "/app", "DB_FILE": "/app/state/db.json", "VERSION": "1.0-RAILWAY", "BOT_TOKEN": "placeholder"}' > /app/config.json

RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p state
RUN if [ ! -f state/db.json ]; then echo '{"users": {}, "votes": {"yes": 0, "no": 0, "unsure": 0}}' > state/db.json; fi
CMD ["python3", "-u", "-c", "print("RAILWAY ENTRY OK", flush=True)"]

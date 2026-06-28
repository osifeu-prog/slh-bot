FROM python:3.11-slim
WORKDIR /app
COPY . /app/

# Create minimal config.json (token will come from env)
RUN echo '{"SUPER_ADMIN": 8789977826, "SITE_DIR": "/app", "DB_FILE": "/app/db.json", "VERSION": "1.0-RAILWAY", "BOT_TOKEN": "placeholder"}' > /app/config.json
ENV BOT_TOKEN=${BOT_TOKEN}

RUN pip install --no-cache-dir -r requirements.txt
RUN if [ ! -f db.json ]; then echo '{"users": {}, "votes": {"yes": 0, "no": 0, "unsure": 0}}' > db.json; fi
CMD ["python3", "-B", "bot.py"]

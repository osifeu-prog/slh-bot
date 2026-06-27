FROM python:3.11-slim

WORKDIR /app

# Copy files
COPY . /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create db.json if missing
RUN if [ ! -f db.json ]; then echo '{"users": {}, "votes": {"yes": 0, "no": 0, "unsure": 0}}' > db.json; fi

# Set token from env
ENV BOT_TOKEN=$BOT_TOKEN
ENV SUPER_ADMIN=8789977826

# Start bot
CMD ["python3", "-B", "bot.py"]

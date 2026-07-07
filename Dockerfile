FROM python:3.11-slim

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir pyTelegramBotAPI psutil requests aiohttp

RUN mkdir -p /app/state

CMD ["python3", "-u", "-B", "bot_stable.py"]

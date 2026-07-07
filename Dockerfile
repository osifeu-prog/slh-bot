FROM python:3.11-slim

WORKDIR /app
COPY . /app/

RUN pip install --no-cache-dir pyTelegramBotAPI psutil requests aiohttp

RUN mkdir -p /app/state

CMD ["sh","-c","echo ==== CONTAINER START ====; pwd; ls -la /app; which python3; python3 --version; python3 -u -B /app/bot_stable.py"]

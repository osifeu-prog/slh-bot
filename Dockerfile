FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN mkdir -p /app/state

CMD ["sh","-c","echo ==== CONTAINER START ====; pwd; ls -la /app; which python3; python3 --version; python3 -u -B /app/bot_stable.py"]

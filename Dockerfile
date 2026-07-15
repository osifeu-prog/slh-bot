FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN echo "=== BUILD CHECK ===" && ls -la /app && test -f /app/bot_stable.py

RUN mkdir -p /app/state

ENTRYPOINT ["python3","-u","-B","/app/bot_stable.py"]

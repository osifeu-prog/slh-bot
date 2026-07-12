FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN echo "=== BUILD CHECK ===" && ls -la /app && test -f /app/bot_stable.py && test -f /app/heb_convert.py && echo "✅ heb_convert.py FOUND in build" || echo "❌ heb_convert.py MISSING in build"

RUN mkdir -p /app/state

ENTRYPOINT ["python3","-u","-B","/app/bot_stable.py"]

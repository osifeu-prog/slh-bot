FROM python:3.11-slim

WORKDIR /app

COPY . /app

CMD ["sh","-c","echo SLH PAUSED && sleep infinity"]

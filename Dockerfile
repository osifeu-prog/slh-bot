FROM python:3.11-slim

WORKDIR /app

COPY . /app/

RUN echo "IMAGE BUILD OK"

CMD ["sh", "-c", "echo CONTAINER SHELL START OK && python3 --version && env | grep RAILWAY && sleep 300"]

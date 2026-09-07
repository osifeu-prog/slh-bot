FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV RUN_BOT=1
CMD ["python", "bot_gateway.py"]

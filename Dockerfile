FROM python:3.11-slim
WORKDIR /app
COPY . /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN if [ ! -f db.json ]; then echo '{"users": {}, "votes": {"yes": 0, "no": 0, "unsure": 0}}' > db.json; fi
CMD ["python3", "-B", "bot.py"]

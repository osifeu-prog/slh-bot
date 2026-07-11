FROM python:3.11-slim

WORKDIR /app

# העתק את כל הפרויקט
COPY . /app/

# התקן תלויות
RUN pip install --no-cache-dir -r requirements.txt

# צור תיקיית state (נפח)
RUN mkdir -p /app/state

# פקודת הפעלה
CMD ["sh","-c","echo ==== CONTAINER START ====; pwd; ls -la /app; which python3; python3 --version; python3 -u -B /app/bot_stable.py"]
# Sat Jul 11 16:47:37 IDT 2026

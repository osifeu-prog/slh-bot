FROM python:3.11-slim

WORKDIR /app

# העתק requirements.txt בנפרד (לפני שאר הקבצים)
COPY requirements.txt /app/requirements.txt

# התקן תלויות
RUN pip install --no-cache-dir -r requirements.txt

# העתק את שאר הפרויקט
COPY . /app/

# צור תיקיית state (נפח)
RUN mkdir -p /app/state

# פקודת הפעלה
CMD ["sh","-c","echo ==== CONTAINER START ====; pwd; ls -la /app; which python3; python3 --version; python3 -u -B /app/bot_stable.py"]

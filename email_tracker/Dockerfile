FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
ENV DB_PATH=/app/output/leads.db
ENV SENDER_PATH=/app/us_email_sender.py
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "60"]

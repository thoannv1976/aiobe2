FROM python:3.11-slim

# Thư viện hệ thống cho PyMuPDF / OCR (tesseract vie cho PDF scan).
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-vie libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run cấp cổng qua $PORT (mặc định 8080). Migrate/seed chạy riêng bằng Cloud Run Job
# (xem deploy/), KHÔNG chạy trong CMD để tránh chạy lại mỗi lần cold-start.
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

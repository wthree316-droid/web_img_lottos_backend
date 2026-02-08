# ใช้ Python เวอร์ชันที่ทันสมัยและเสถียร
FROM python:3.11-slim

# ตั้ง Folder ทำงาน
WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ก๊อปปี้โค้ดทั้งหมดในโฟลเดอร์ปัจจุบันไปที่ Docker
COPY . .

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# ✅ Security: สร้าง non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Cloud Run จะส่งค่า PORT มาให้ทาง Environment Variable
# คำสั่งนี้จะรัน Uvicorn ให้ฟัง Port นั้น
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
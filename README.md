# 🚀 Lottery Generator Backend API

FastAPI backend สำหรับระบบสร้างภาพหวยอัตโนมัติ

## 🛠️ Tech Stack

- **Framework:** FastAPI
- **Database:** Supabase (PostgreSQL)
- **Storage:** Supabase Storage
- **Auth:** Password hashing with bcrypt
- **Deployment:** Docker + Google Cloud Run

## 📦 Installation

```bash
# 1. สร้าง virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# หรือ
venv\Scripts\activate  # Windows

# 2. ติดตั้ง dependencies
pip install -r requirements.txt

# 3. ตั้งค่า environment variables
cp .env.example .env
# แก้ไขค่าใน .env ให้ตรงกับ Supabase project ของคุณ
```

## 🔐 Security Setup

### First Time Setup: Password Migration

หากคุณมี users ที่เก็บ password แบบ plain text อยู่แล้ว ให้รัน migration script:

```bash
python migrate_passwords.py
```

Script นี้จะ:
- เช็คว่า password ไหนเป็น plain text
- Hash ด้วย bcrypt
- Update กลับเข้า database

⚠️ **สำคัญ:** รันครั้งเดียวหลัง deploy โค้ดใหม่เท่านั้น!

## 🚀 Running Locally

```bash
# Development mode (auto-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8080

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8080 --workers 4
```

## 🐳 Docker

```bash
# Build image
docker build -t lottery-api .

# Run container
docker run -p 8080:8080 \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_KEY=your_key \
  -e ALLOWED_ORIGINS=https://your-frontend.vercel.app \
  lottery-api
```

## 📡 API Endpoints

### Health Check
- `GET /` - Root endpoint
- `GET /health` - Health check (for monitoring)

### Authentication
- `POST /api/login` - Login (returns user data without password)

### Lottery Generation
- `POST /api/generate` - Generate lottery numbers
- `GET /api/lotteries` - Get all lotteries
- `GET /api/lotteries/{id}` - Get lottery details

### Templates
- `GET /api/templates` - Get all templates
- `GET /api/templates/{id}` - Get template by ID
- `POST /api/templates` - Create template (Admin)
- `PUT /api/templates/{id}` - Update template (Admin)
- `DELETE /api/templates/{id}` - Delete template (Admin)

### Users
- `GET /api/users` - Get all users (Admin)
- `POST /api/users` - Create user (Admin)
- `PUT /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Delete user (Admin)

### Upload
- `POST /api/upload` - Upload image to Supabase Storage

## 🔒 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Supabase project URL | ✅ |
| `SUPABASE_KEY` | Supabase service role key | ✅ |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | ✅ |

## 🧪 Testing

```bash
# ทดสอบ health endpoint
curl http://localhost:8080/health

# ทดสอบ login
curl -X POST http://localhost:8080/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}'
```

## 📝 Notes

- Password ทุกตัวถูก hash ด้วย bcrypt (cost factor: 12)
- CORS ถูกจำกัดเฉพาะ domains ที่ระบุใน `ALLOWED_ORIGINS`
- Randomization ใช้ `secrets` module สำหรับความปลอดภัย
- Health check endpoint สำหรับ Docker/Kubernetes monitoring

## 🐛 Common Issues

### Issue: CORS Error
**Solution:** ตรวจสอบว่าตั้งค่า `ALLOWED_ORIGINS` ใน environment variables ถูกต้อง

### Issue: Login ล้มเหลว
**Solution:** ตรวจสอบว่ารัน `migrate_passwords.py` แล้วหรือยัง

### Issue: Database Connection Failed
**Solution:** ตรวจสอบ `SUPABASE_URL` และ `SUPABASE_KEY` ใน .env

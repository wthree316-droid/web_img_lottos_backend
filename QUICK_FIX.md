# 🔧 QUICK FIX: ModuleNotFoundError: No module named 'passlib'

## ปัญหา
```
ModuleNotFoundError: No module named 'passlib'
```

หลังจากแก้ไข `requirements.txt` ต้องติดตั้ง dependencies ใหม่

---

## ✅ วิธีแก้ไข (เลือก 1 วิธี)

### วิธีที่ 1: ใช้ Script อัตโนมัติ (แนะนำ)

**สำหรับ PowerShell:**
```powershell
cd backend
.\install_deps.ps1
```

**สำหรับ CMD:**
```cmd
cd backend
install_deps.bat
```

---

### วิธีที่ 2: ติดตั้งเอง (Manual)

```powershell
# 1. เข้า backend directory
cd backend

# 2. Activate virtual environment
.\venv\Scripts\Activate

# 3. Upgrade pip
python -m pip install --upgrade pip

# 4. ติดตั้ง dependencies
pip install -r requirements.txt
```

---

### วิธีที่ 3: ติดตั้งแค่ passlib (Quick Fix)

```powershell
cd backend
.\venv\Scripts\Activate
pip install passlib[bcrypt]
```

---

## 🧪 ทดสอบว่าติดตั้งสำเร็จ

```powershell
python -c "import passlib; print('✅ Passlib OK')"
python -c "import fastapi; print('✅ FastAPI OK')"
```

---

## 🚀 รัน Server

```powershell
uvicorn main:app --reload
```

ควรเห็น:
```
✅ Supabase Connected Successfully!
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## 🐛 ถ้ายังมีปัญหา

### Error: Permission denied

**แก้ไข:**
```powershell
# ปิด VS Code/Cursor
# เปิด PowerShell ใหม่ด้วย Administrator
cd D:\Desktop\project_lottos_img\backend
.\venv\Scripts\Activate
pip install --user -r requirements.txt
```

### Error: venv not found

**แก้ไข:**
```powershell
# สร้าง virtual environment ใหม่
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
```

### Error: Python version mismatch

**แก้ไข:**
```powershell
# ตรวจสอบ Python version
python --version  # ต้องเป็น 3.9 ขึ้นไป

# ถ้าต่ำกว่า ให้ติดตั้ง Python ใหม่
# Download from: https://www.python.org/downloads/
```

---

## ✅ Checklist

หลังติดตั้งเสร็จ ควรมี:

- [ ] passlib installed
- [ ] bcrypt installed
- [ ] fastapi installed
- [ ] uvicorn installed
- [ ] supabase installed
- [ ] Server รันได้โดยไม่มี error

---

## 📝 Next Steps

หลังจาก server รันได้แล้ว:

1. ✅ รัน password migration:
   ```powershell
   python migrate_passwords.py
   ```

2. ✅ ทดสอบ API:
   ```powershell
   # เปิดเบราว์เซอร์ไปที่
   http://127.0.0.1:8000/health
   ```

3. ✅ ทดสอบ login:
   ```powershell
   curl -X POST http://127.0.0.1:8000/api/login `
     -H "Content-Type: application/json" `
     -d '{"username":"admin","password":"1234"}'
   ```

---

**สร้างไฟล์นี้:** 2026-02-08  
**Status:** ✅ Ready to use

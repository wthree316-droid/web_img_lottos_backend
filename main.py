from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from datetime import datetime

# ✅ 1. นำเข้า Router ทั้งหมดที่จัดระเบียบไว้
from routers import auth, users, lotteries, templates, config, generate, assets

load_dotenv()

app = FastAPI(title="Lottery Studio API", version="2.0")

# ✅ 2. ตั้งค่า CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 3. เสียบปลั๊ก Router (เหมือนการต่อจิ๊กซอว์)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(lotteries.router)
app.include_router(templates.router)
app.include_router(config.router)
app.include_router(generate.router)
app.include_router(assets.router)

# ✅ 4. Base Routes สำหรับเช็คสถานะเซิร์ฟเวอร์
@app.get("/")
def read_root():
    return {"message": "Lottery API is running! 🚀 (Modular Mode)"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
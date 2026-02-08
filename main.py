from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from database import supabase 
from schemas import GenerateRequest, GenerateResponse, TemplateCreate, UploadResponse, UserLogin, UserCreate, UserUpdate
from logic import LotteryLogic
from passlib.context import CryptContext

from supabase import create_client, Client
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime
import hashlib

# ตั้งค่าสำหรับ Hash Password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def safe_hash_password(password: str) -> str:
    """
    Hash password โดยรองรับความยาวที่เกิน 72 bytes
    bcrypt มีข้อจำกัดที่ 72 bytes ดังนั้นถ้า password ยาวเกิน
    เราจะ hash ด้วย SHA256 ก่อน แล้วค่อย hash ด้วย bcrypt
    """
    password_bytes = password.encode('utf-8')
    
    if len(password_bytes) > 72:
        # ถ้ายาวเกิน 72 bytes ให้ hash ด้วย SHA256 ก่อน
        sha_hash = hashlib.sha256(password_bytes).hexdigest()
        return pwd_context.hash(sha_hash)
    else:
        # ถ้าไม่เกิน 72 bytes ก็ hash ตรงๆ
        return pwd_context.hash(password)

def safe_verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password โดยรองรับทั้ง password ปกติและ password ที่ยาวเกิน 72 bytes
    """
    password_bytes = plain_password.encode('utf-8')
    
    # ลองวิธีปกติก่อน
    try:
        if pwd_context.verify(plain_password, hashed_password):
            return True
    except:
        pass
    
    # ถ้าไม่ได้ ลอง SHA256+bcrypt (สำหรับ password ที่ยาว)
    if len(password_bytes) > 72:
        try:
            sha_hash = hashlib.sha256(password_bytes).hexdigest()
            return pwd_context.verify(sha_hash, hashed_password)
        except:
            pass
    
    return False

app = FastAPI()

# 🔓 เปิด CORS ให้ Frontend เข้าถึงได้ (ระบุ Domain ชัดเจนเพื่อความปลอดภัย)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # ✅ แก้ไข: ใช้ environment variable แทน wildcard
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

@app.get("/")
def read_root():
    return {"message": "Lottery API is running! 🚀"}

@app.get("/health")
def health_check():
    """Health check endpoint สำหรับ monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "lottery-api"
    }

@app.post("/api/generate", response_model=GenerateResponse)
def generate_numbers(request: GenerateRequest):
    """
    API หลัก: รับ Template + Seed -> ส่งเลขชุดกลับไป
    """
    try:
        # 1. เรียกใช้ Logic Engine
        engine = LotteryLogic(seed=request.user_seed)
        
        results = {}
        
        # 2. วนลูปเช็ค Slot ทุกอันที่ส่งมา
        for slot in request.slot_configs:
            # เราจะสนใจเฉพาะ Slot ที่เป็น 'user_input' และมี data_key
            if slot.get("slot_type") == "user_input" and slot.get("data_key"):
                key = slot["data_key"]
                
                # ✅ แก้ไข: ใช้ ID ของ Slot เป็น Key ในการส่งกลับ (เพื่อให้แต่ละกล่องได้เลขไม่ซ้ำกัน)
                # แม้จะเป็น data_key เดียวกัน แต่ engine.generate จะสุ่มใหม่ทุกรอบ
                slot_id = slot.get("id")
                if slot_id:
                    results[slot_id] = engine.generate(key)

        return {"results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/templates")
def get_templates():
    """
    API สำหรับดึงรายการแม่พิมพ์ทั้งหมดไปแสดงที่หน้า Dashboard
    """
    try:
        # ดึงข้อมูลจากตาราง templates เรียงตามล่าสุด
        response = supabase.table("templates").select("*").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/templates/{template_id}")
def get_template(template_id: str):
    """
    API ดึงข้อมูล Template รายตัว พร้อม Slot ทั้งหมด
    """
    try:
        # ใช้ Supabase Join ตาราง templates กับ template_slots
        response = supabase.table("templates")\
            .select("*, template_slots(*)")\
            .eq("id", template_id)\
            .single()\
            .execute()
            
        if not response.data:
            raise HTTPException(status_code=404, detail="Template not found")
            
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/templates")
def create_template(request: TemplateCreate):
    try:
        # 1. บันทึกตัวแม่ (Template)
        # ✅ แก้ไข: Map จาก request.width -> base_width ของ Database
        template_data = {
            "name": request.name,
            "base_width": request.width,   # ตรงนี้ต้องส่งเข้า base_width
            "base_height": request.height, # ตรงนี้ต้องส่งเข้า base_height
            "background_url": request.background_url,
            "is_active": True
        }
        
        res_template = supabase.table("templates").insert(template_data).execute()
        
        if not res_template.data:
            raise HTTPException(status_code=500, detail="Failed to save template")
        
        new_template_id = res_template.data[0]['id']

        # 2. เตรียมข้อมูลลูกๆ (Slots)
        slots_data = []
        for slot in request.slots:
            slots_data.append({
                "template_id": new_template_id,
                "slot_type": slot.type,    
                "label_text": slot.content, 
                "data_key": slot.data_key,
                "pos_x": slot.x,           
                "pos_y": slot.y,           
                "width": slot.width,
                "height": slot.height,
                "style_config": slot.style, 
                "z_index": 1
            })
        
        # 3. บันทึกลูกๆ
        if slots_data:
            supabase.table("template_slots").insert(slots_data).execute()

        return {"message": "Saved successfully!", "id": new_template_id}

    except Exception as e:
        print("Error details:", e) # ปริ้นท์ดูเผื่อมี error อื่น
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/templates/{template_id}")
def update_template(template_id: str, request: TemplateCreate):
    """
    API แก้ไขแม่พิมพ์: อัปเดตข้อมูลแม่ และล้างไพ่ลงข้อมูลลูกใหม่
    """
    try:
        # 1. อัปเดตตัวแม่ (Templates)
        template_data = {
            "name": request.name,
            "base_width": request.width,
            "base_height": request.height,
            "background_url": request.background_url,
            "updated_at": "now()" # อัปเดตเวลาแก้ไข
        }
        
        supabase.table("templates").update(template_data).eq("id", template_id).execute()

        # 2. ล้างบาง! ลบ Slot เก่าทิ้งให้เกลี้ยง (เดี๋ยวสร้างใหม่ทับ)
        supabase.table("template_slots").delete().eq("template_id", template_id).execute()

        # 3. สร้าง Slot ใหม่ (เหมือนตอน Create)
        slots_data = []
        for slot in request.slots:
            slots_data.append({
                "template_id": template_id, # ใช้ ID เดิม
                "slot_type": slot.type,
                "label_text": slot.content,
                "data_key": slot.data_key,
                "pos_x": slot.x,
                "pos_y": slot.y,
                "width": slot.width,
                "height": slot.height,
                "style_config": slot.style,
                "z_index": 1
            })
        
        if slots_data:
            supabase.table("template_slots").insert(slots_data).execute()

        return {"message": "Updated successfully!"}

    except Exception as e:
        print("Error details:", e)
        raise HTTPException(status_code=500, detail=str(e))    

@app.delete("/api/templates/{template_id}")
def delete_template(template_id: str):
    """
    API ลบแม่พิมพ์ (Slots ข้างในจะหายไปเองเพราะ Cascade)
    """
    try:
        # สั่งลบที่ตาราง templates โดยระบุ ID
        res = supabase.table("templates").delete().eq("id", template_id).execute()
        
        # เช็คว่าลบจริงไหม (ถ้า data ว่างแปลว่าหาไม่เจอ)
        if not res.data:
             raise HTTPException(status_code=404, detail="Template not found")

        return {"message": "Deleted successfully"}

    except Exception as e:
        print("Delete Error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """
    รับไฟล์ภาพ -> อัปขึ้น Supabase Storage -> คืนค่า URL
    """
    try:
        # 1. อ่านไฟล์
        file_content = await file.read()
        
        # 2. ตั้งชื่อไฟล์ใหม่ (กันชื่อซ้ำ) เช่น "backgrounds/uuid-filename.png"
        file_ext = file.filename.split(".")[-1]
        file_path = f"backgrounds/{uuid.uuid4()}.{file_ext}"
        
        # 3. อัปโหลดขึ้น Bucket ชื่อ 'lotto-assets' (ต้องตรงกับที่สร้างใน Step 1)
        bucket_name = "lotto-assets"
        res = supabase.storage.from_(bucket_name).upload(
            path=file_path,
            file=file_content,
            file_options={"content-type": file.content_type}
        )
        
        # 4. ขอ URL แบบ Public
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
        
        return {"url": public_url}

    except Exception as e:
        print("Upload Error:", e)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/lotteries")
def get_lotteries():
    """ดึงรายชื่อหวยทั้งหมด (สำหรับแสดงเมนู)"""
    try:
        # ดึงรายชื่อหวย และ join เอาข้อมูล Template มาด้วย (เผื่อเอารูปพื้นหลังมาโชว์)
        response = supabase.table("lotteries")\
            .select("*, templates(background_url, base_width, base_height)")\
            .eq("is_active", True)\
            .execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ไฟล์: backend/main.py

@app.get("/api/lotteries/{lottery_id}")
def get_lottery_details(lottery_id: str):
    """
    ดึงข้อมูลหวย 1 ตัว + Template ที่มันใช้ (พร้อมระบบกันตาย ถ้า Template หาย)
    """
    try:
        # 1. ดึงข้อมูลหวยก่อน
        lottery_res = supabase.table("lotteries").select("*").eq("id", lottery_id).single().execute()
        if not lottery_res.data:
            raise HTTPException(status_code=404, detail="Lottery not found")
        
        lottery = lottery_res.data
        template_id = lottery.get('template_id') # ใช้ .get() กันเหนียว

        # 🛡️ Defense 1: ถ้าใน DB ค่า template_id เป็น NULL (ไม่มีการผูก)
        if not template_id:
             # ✅ ยอมให้เป็น NULL ได้ เพื่อให้ Frontend ไปดึง Template ของ User มาใช้แทน
             return {
                 "lottery": lottery,
                 "template": None
             }

        # 2. ไปดึงข้อมูล Template
        try:
            template_res = supabase.table("templates")\
                .select("*, template_slots(*)")\
                .eq("id", template_id)\
                .single()\
                .execute()
        except Exception:
            # 🛡️ Defense 2: ถ้าค้นหา ID ไม่เจอ (เช่น ถูกลบไปแล้ว)
             return {
                 "lottery": lottery,
                 "template": None
             }

        if not template_res.data:
             return {
                 "lottery": lottery,
                 "template": None
             }

        # 3. มัดรวมข้อมูลส่งกลับไป
        return {
            "lottery": lottery,
            "template": template_res.data
        }

    except HTTPException as he:
        raise he # ถ้าเป็น Error ที่เราตั้งใจ throw ให้ส่งออกไปเลย
    except Exception as e:
        print("System Error:", e)
        raise HTTPException(status_code=500, detail=str(e))

# --- User Management APIs ---

@app.post("/api/login")
def login(request: UserLogin):
    """ตรวจสอบ User/Pass และคืนค่าข้อมูลผู้ใช้"""
    try:
        # 1. ดึงข้อมูล user จาก username ก่อน
        user = supabase.table("users")\
            .select("*")\
            .eq("username", request.username)\
            .single()\
            .execute()
            
        if not user.data:
            raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        
        # 2. ✅ แก้ไข: ตรวจสอบ password ด้วย safe_verify_password
        if not safe_verify_password(request.password, user.data['password']):
            raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
            
        # 3. ส่งข้อมูล user กลับไป (ไม่ส่ง password)
        user_data = {k: v for k, v in user.data.items() if k != 'password'}
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login Error: {e}")
        raise HTTPException(status_code=401, detail="Login failed")

@app.get("/api/users")
def get_users():
    """(Admin) ดึงรายชื่อสมาชิกทั้งหมด"""
    try:
        # เรียงตามวันที่สร้างล่าสุด
        res = supabase.table("users").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users")
def create_user(request: UserCreate):
    """(Admin) สร้างสมาชิกใหม่"""
    try:
        # ✅ แก้ไข: Hash password ก่อนบันทึก (รองรับ password ยาว)
        hashed_password = safe_hash_password(request.password)
        
        user_data = {
            "username": request.username,
            "password": hashed_password,  # เก็บเป็น hash แทน plain text
            "name": request.name,
            "role": request.role,
            "assigned_template_id": request.assigned_template_id
        }
        res = supabase.table("users").insert(user_data).execute()
        return {"message": "User created successfully"}
    except Exception as e:
        # เช็คว่าชื่อซ้ำไหม
        if "unique constraint" in str(e).lower() or "duplicate" in str(e).lower():
             raise HTTPException(status_code=400, detail="Username นี้มีคนใช้แล้ว")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{user_id}")
def update_user(user_id: str, request: UserUpdate):
    """(Admin/Member) อัปเดตข้อมูล (ชื่อ, รหัส, แม่พิมพ์)"""
    try:
        update_data = {}
        if request.name: 
            update_data["name"] = request.name
        if request.password: 
            # ✅ แก้ไข: Hash password ก่อน update (รองรับ password ยาว)
            update_data["password"] = safe_hash_password(request.password)
        if request.assigned_template_id: 
            update_data["assigned_template_id"] = request.assigned_template_id
        
        # ถ้าไม่มีอะไรส่งมาเลย ก็ไม่ต้องทำอะไร
        if not update_data:
            return {"message": "Nothing to update"}

        supabase.table("users").update(update_data).eq("id", user_id).execute()
        return {"message": "User updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
def delete_user(user_id: str):
    """(Admin) ลบสมาชิก"""
    try:
        supabase.table("users").delete().eq("id", user_id).execute()
        return {"message": "User deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# วิธีรัน: uvicorn main:app --reload
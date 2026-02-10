from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from database import supabase 
from schemas import (
    GenerateRequest, GenerateResponse, TemplateCreate, UploadResponse, 
    UserLogin, UserCreate, UserUpdate, GlobalConfigUpdate, GlobalConfigResponse,
    LotteryUpdate, LotteryCreate
)
from logic import LotteryLogic
from passlib.context import CryptContext

from supabase import create_client, Client
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime
import hashlib

load_dotenv()

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
    allow_origins=ALLOWED_ORIGINS,  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

@app.get("/api/global-configs", response_model=GlobalConfigResponse)
def get_global_configs():
    """ดึงค่ากลาง (QR Code, Line ID) - เปิด Public ให้ Frontend ดึงไปโชว์ได้"""
    try:
        response = supabase.table("global_configs").select("*").execute()
        configs = {item['key']: item['value'] for item in response.data}
        return {
            "qr_code_url": configs.get("qr_code_url", ""),
            "line_id": configs.get("line_id", "")
        }
    except Exception as e:
        # กรณีไม่เจอ table หรือ error อื่นๆ ให้คืนค่าว่างไปก่อน
        return {"qr_code_url": "", "line_id": ""}

@app.put("/api/global-configs")
def update_global_configs(config: GlobalConfigUpdate):
    """อัปเดตค่ากลาง"""
    try:
        if config.qr_code_url is not None:
            supabase.table("global_configs").upsert({"key": "qr_code_url", "value": config.qr_code_url}).execute()
        if config.line_id is not None:
            supabase.table("global_configs").upsert({"key": "line_id", "value": config.line_id}).execute()
        return {"message": "Updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate", response_model=GenerateResponse)
def generate_numbers(request: GenerateRequest):
    """
    API หลัก: รับ Template + Seed -> ส่งเลขชุดกลับไป
    รวมถึงเติมค่า Global Configs (QR Code, Line ID) อัตโนมัติ
    """
    try:
        # 1. เรียกใช้ Logic Engine
        engine = LotteryLogic(seed=request.user_seed)
        
        # 2. เตรียม Global Configs
        global_data = {}
        try:
            g_res = supabase.table("global_configs").select("*").execute()
            for item in g_res.data:
                global_data[item['key']] = item['value']
        except:
            pass

        results = {}
        
        # 3. วนลูปเช็ค Slot ทุกอันที่ส่งมา
        for slot in request.slot_configs:
            slot_id = slot.get("id")
            slot_type = slot.get("slot_type")
            data_key = slot.get("data_key")

            # Case A: User Input / Auto Data (สุ่มเลข)
            if slot_type == "user_input" and data_key:
                if slot_id:
                    results[slot_id] = engine.generate(data_key)
            
            # Case B: QR Code (เติม URL อัตโนมัติ)
            elif slot_type == "qr_code":
                if slot_id:
                    results[slot_id] = global_data.get("qr_code_url", "")
            
            # Case C: Static Text (เช่น LINE ID)
            elif slot_type == "static_text" and data_key == "line_id":
                if slot_id:
                    results[slot_id] = global_data.get("line_id", "")

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
    API ดึงข้อมูล Template รายตัว พร้อม Slot และ Backgrounds ทั้งหมด
    """
    try:
        # ใช้ Supabase Join ตาราง templates กับ template_slots และ template_backgrounds
        response = supabase.table("templates")\
            .select("*, template_slots(*), template_backgrounds(*)")\
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
        template_data = {
            "name": request.name,
            "base_width": request.width,   
            "base_height": request.height, 
            "background_url": request.background_url,
            "is_master": request.is_master,
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
        
        # 3. บันทึกลูกๆ (Slots)
        if slots_data:
            supabase.table("template_slots").insert(slots_data).execute()

        # 4. บันทึกพื้นหลังทางเลือก (Backgrounds)
        backgrounds_data = []
        if request.backgrounds:
            for bg in request.backgrounds:
                backgrounds_data.append({
                    "template_id": new_template_id,
                    "name": bg.name,
                    "url": bg.url
                })
            supabase.table("template_backgrounds").insert(backgrounds_data).execute()

        return {"message": "Saved successfully!", "id": new_template_id}

    except Exception as e:
        print("Error details:", e) 
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/templates/{template_id}")
def update_template(template_id: str, request: TemplateCreate):
    """
    API แก้ไขแม่พิมพ์: อัปเดตข้อมูลแม่, ล้างไพ่ Slots/Backgrounds เก่า แล้วลงใหม่
    """
    try:
        # 1. อัปเดตตัวแม่ (Templates)
        template_data = {
            "name": request.name,
            "base_width": request.width,
            "base_height": request.height,
            "background_url": request.background_url,
            "is_master": request.is_master,
            "updated_at": "now()" 
        }
        
        supabase.table("templates").update(template_data).eq("id", template_id).execute()

        # 2. ล้างข้อมูลลูกเก่าทิ้ง (Slots & Backgrounds)
        supabase.table("template_slots").delete().eq("template_id", template_id).execute()
        supabase.table("template_backgrounds").delete().eq("template_id", template_id).execute()

        # 3. สร้าง Slot ใหม่
        slots_data = []
        for slot in request.slots:
            slots_data.append({
                "template_id": template_id, 
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

        # 4. สร้าง Backgrounds ใหม่
        backgrounds_data = []
        if request.backgrounds:
            for bg in request.backgrounds:
                backgrounds_data.append({
                    "template_id": template_id,
                    "name": bg.name,
                    "url": bg.url
                })
            supabase.table("template_backgrounds").insert(backgrounds_data).execute()

        return {"message": "Updated successfully!"}

    except Exception as e:
        print("Error details:", e)
        raise HTTPException(status_code=500, detail=str(e))    

@app.delete("/api/templates/{template_id}")
def delete_template(template_id: str):
    """
    API ลบแม่พิมพ์ (Slots/Backgrounds ข้างในจะหายไปเองเพราะ Cascade)
    """
    try:
        res = supabase.table("templates").delete().eq("id", template_id).execute()
        
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
        file_content = await file.read()
        file_ext = file.filename.split(".")[-1]
        file_path = f"backgrounds/{uuid.uuid4()}.{file_ext}"
        bucket_name = "lotto-assets"
        
        res = supabase.storage.from_(bucket_name).upload(
            path=file_path,
            file=file_content,
            file_options={"content-type": file.content_type}
        )
        
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
        
        return {"url": public_url}

    except Exception as e:
        print("Upload Error:", e)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/lotteries")
def get_lotteries(search: str = Query(None)):
    """
    ดึงรายชื่อหวยทั้งหมด พร้อม Sorting และ Search
    """
    try:
        query = supabase.table("lotteries")\
            .select("*, templates(background_url, base_width, base_height)")\
            .eq("is_active", True)
            
        if search:
            query = query.ilike("name", f"%{search}%")
            
        # เรียงตามเวลาปิดรับ (ถ้ามี) ถ้าไม่มีเอาไว้ท้ายสุด
        response = query.order("closing_time", desc=False).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/lotteries/{lottery_id}")
def get_lottery_details(lottery_id: str, user_id: str = None):
    """
    ดึงข้อมูลหวย 1 ตัว + Template (Override by User, Fallback by Lottery, Fallback by System)
    """
    try:
        lottery_res = supabase.table("lotteries").select("*").eq("id", lottery_id).single().execute()
        if not lottery_res.data:
            raise HTTPException(status_code=404, detail="Lottery not found")
        
        lottery = lottery_res.data
        target_template_id = None

        # 1. Priority: User Template
        if user_id:
            try:
                user_res = supabase.table("users").select("assigned_template_id").eq("id", user_id).single().execute()
                if user_res.data and user_res.data.get('assigned_template_id'):
                    target_template_id = user_res.data['assigned_template_id']
            except Exception:
                pass

        # 2. Priority: Lottery Template
        if not target_template_id:
            target_template_id = lottery.get('template_id')

        # 3. Priority: System Default (Last Active Template)
        if not target_template_id:
            try:
                latest_res = supabase.table("templates").select("id").eq("is_active", True).order("created_at", desc=True).limit(1).execute()
                if latest_res.data:
                    target_template_id = latest_res.data[0]['id']
            except Exception:
                pass

        if not target_template_id:
             # ยอมคืนค่าว่างถ้าไม่มีจริงๆ ให้ Frontend จัดการ
             return {"lottery": lottery, "template": None}

        # ดึงข้อมูล Template + Slots + Backgrounds
        try:
            template_res = supabase.table("templates")\
                .select("*, template_slots(*), template_backgrounds(*)")\
                .eq("id", target_template_id)\
                .single()\
                .execute()
        except Exception:
             return {"lottery": lottery, "template": None}

        if not template_res.data:
             return {"lottery": lottery, "template": None}

        return {
            "lottery": lottery,
            "template": template_res.data,
            "used_template_id": target_template_id
        }

    except HTTPException as he:
        raise he 
    except Exception as e:
        print("System Error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/lotteries/{lottery_id}")
def update_lottery(lottery_id: str, request: LotteryUpdate):
    try:
        update_data = {}
        if request.name is not None: # ✅ เพิ่ม logic อัปเดตชื่อ
            update_data["name"] = request.name
        if request.closing_time is not None:
            update_data["closing_time"] = request.closing_time.isoformat()
        if request.is_active is not None:
            update_data["is_active"] = request.is_active
        if request.template_id is not None:
            # ถ้าส่ง string ว่างมา ให้ set เป็น null
            update_data["template_id"] = request.template_id if request.template_id else None
            
        if not update_data:
            return {"message": "Nothing to update"}

        supabase.table("lotteries").update(update_data).eq("id", lottery_id).execute()
        return {"message": "Lottery updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lotteries")
def create_lottery(request: LotteryCreate):
    try:
        data = {
            "name": request.name,
            "template_id": request.template_id if request.template_id else None,
            "closing_time": request.closing_time.isoformat() if request.closing_time else None,
            "is_active": request.is_active
        }
        res = supabase.table("lotteries").insert(data).execute()
        return {"message": "Lottery created successfully", "data": res.data}
    except Exception as e:
        if "unique constraint" in str(e).lower() or "duplicate" in str(e).lower():
             raise HTTPException(status_code=400, detail="ชื่อหวยนี้มีอยู่แล้ว")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/lotteries/{lottery_id}")
def delete_lottery(lottery_id: str):
    try:
        supabase.table("lotteries").delete().eq("id", lottery_id).execute()
        return {"message": "Lottery deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- User Management APIs ---

@app.post("/api/login")
def login(request: UserLogin):
    try:
        user = supabase.table("users")\
            .select("*")\
            .eq("username", request.username)\
            .single()\
            .execute()
            
        if not user.data:
            raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        
        if not safe_verify_password(request.password, user.data['password']):
            raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
            
        user_data = {k: v for k, v in user.data.items() if k != 'password'}
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login Error: {e}")
        raise HTTPException(status_code=401, detail="Login failed")

@app.get("/api/users")
def get_users():
    try:
        res = supabase.table("users").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{user_id}")
def get_user(user_id: str):
    try:
        res = supabase.table("users").select("*").eq("id", user_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="User not found")
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users")
def create_user(request: UserCreate):
    try:
        hashed_password = safe_hash_password(request.password)
        
        user_data = {
            "username": request.username,
            "password": hashed_password, 
            "name": request.name,
            "role": request.role,
            "assigned_template_id": request.assigned_template_id,
            "allowed_template_ids": request.allowed_template_ids
        }
        supabase.table("users").insert(user_data).execute()
        return {"message": "User created successfully"}
    except Exception as e:
        if "unique constraint" in str(e).lower() or "duplicate" in str(e).lower():
             raise HTTPException(status_code=400, detail="Username นี้มีคนใช้แล้ว")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{user_id}")
def update_user(user_id: str, request: UserUpdate):
    try:
        update_data = {}
        if request.name: 
            update_data["name"] = request.name
        if request.password: 
            update_data["password"] = safe_hash_password(request.password)
        if request.assigned_template_id is not None:
            update_data["assigned_template_id"] = request.assigned_template_id if request.assigned_template_id else None
        if request.allowed_template_ids is not None:
            update_data["allowed_template_ids"] = request.allowed_template_ids
        
        if not update_data:
            return {"message": "Nothing to update"}

        supabase.table("users").update(update_data).eq("id", user_id).execute()
        return {"message": "User updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
def delete_user(user_id: str):
    try:
        supabase.table("users").delete().eq("id", user_id).execute()
        return {"message": "User deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# วิธีรัน: uvicorn main:app --reload
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

import os
from dotenv import load_dotenv
import uuid
from datetime import datetime
import hashlib
import time
import random

load_dotenv()

# ตั้งค่าสำหรับ Hash Password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def safe_hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        sha_hash = hashlib.sha256(password_bytes).hexdigest()
        return pwd_context.hash(sha_hash)
    else:
        return pwd_context.hash(password)

def safe_verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode('utf-8')
    try:
        if pwd_context.verify(plain_password, hashed_password): return True
    except: pass
    if len(password_bytes) > 72:
        try:
            sha_hash = hashlib.sha256(password_bytes).hexdigest()
            return pwd_context.verify(sha_hash, hashed_password)
        except: pass
    return False

# ✅ Helper Function: Retry Logic สำหรับ Supabase
def execute_supabase(query_builder, max_retries=3):
    """
    หุ้มคำสั่ง Supabase execute() ด้วยระบบ Retry
    เพื่อป้องกัน WinError 10035 หรือ Network Error ชั่วคราว
    """
    last_error = None
    for i in range(max_retries):
        try:
            return query_builder.execute()
        except Exception as e:
            last_error = e
            # ถ้าเป็น Error เกี่ยวกับ Socket/SSL ให้รอแป๊บแล้วลองใหม่
            if "10035" in str(e) or "socket" in str(e).lower() or "ssl" in str(e).lower():
                time.sleep(0.1 + (random.random() * 0.2)) # รอ 0.1 - 0.3 วินาที
                continue
            raise e # ถ้าเป็น Error อื่น (เช่น SQL ผิด) ให้โยนทิ้งเลย
    raise last_error

app = FastAPI()

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
    return {"message": "Lottery API is running! 🚀 (Robust Mode)"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# --- Global Configs ---
@app.get("/api/global-configs", response_model=GlobalConfigResponse)
def get_global_configs():
    try:
        response = execute_supabase(supabase.table("global_configs").select("*"))
        configs = {item['key']: item['value'] for item in response.data}
        return {
            "qr_code_url": configs.get("qr_code_url", ""),
            "line_id": configs.get("line_id", "")
        }
    except Exception as e:
        return {"qr_code_url": "", "line_id": ""}

@app.put("/api/global-configs")
def update_global_configs(config: GlobalConfigUpdate):
    try:
        if config.qr_code_url is not None:
            execute_supabase(supabase.table("global_configs").upsert({"key": "qr_code_url", "value": config.qr_code_url}))
        if config.line_id is not None:
            execute_supabase(supabase.table("global_configs").upsert({"key": "line_id", "value": config.line_id}))
        return {"message": "Updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- GENERATE ENGINE ---
@app.post("/api/generate", response_model=GenerateResponse)
def generate_numbers(request: GenerateRequest):
    try:
        engine = LotteryLogic(seed=request.user_seed)
        final_qr = ""
        final_line = ""

        # 1. User Override (Priority 1)
        if request.target_user_id:
            try:
                u_res = execute_supabase(supabase.table("users").select("custom_qr_code_url, custom_line_id").eq("id", request.target_user_id).limit(1))
                if u_res.data and len(u_res.data) > 0:
                    user_data = u_res.data[0]
                    if user_data.get("custom_qr_code_url"):
                        final_qr = user_data["custom_qr_code_url"]
                    if user_data.get("custom_line_id"):
                        final_line = user_data["custom_line_id"]
            except: pass

        results = {}
        for slot in request.slot_configs:
            slot_id = slot.get("id")
            slot_type = slot.get("slot_type")
            data_key = slot.get("data_key")

            if slot_type == "user_input" and data_key:
                if slot_id: results[slot_id] = engine.generate(data_key)
            elif slot_type == "qr_code":
                if slot_id: results[slot_id] = final_qr
            elif slot_type == "static_text" and data_key == "line_id":
                if slot_id: results[slot_id] = final_line

        return {"results": results}
    except Exception as e:
        print(f"Generate Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Templates ---
@app.get("/api/templates")
def get_templates(owner_id: str = Query(None)):
    try:
        query = supabase.table("templates").select("*").order("created_at", desc=True)
        if owner_id:
            query = query.or_(f"owner_id.eq.{owner_id},owner_id.is.null")
        response = execute_supabase(query)
        return response.data
    except Exception as e:
        print(f"Get Templates Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/templates/{template_id}")
def get_template(template_id: str):
    try:
        response = execute_supabase(
            supabase.table("templates")
            .select("*, template_slots(*), template_backgrounds(*)")
            .eq("id", template_id)
            .limit(1)
        )
            
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Template not found")
            
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get Template Detail Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/templates")
def create_template(request: TemplateCreate):
    try:
        template_data = {
            "name": request.name,
            "base_width": request.width,   
            "base_height": request.height, 
            "background_url": request.background_url,
            "is_master": request.is_master,
            "owner_id": None, # Default None
            "is_active": True
        }
        res_template = execute_supabase(supabase.table("templates").insert(template_data))
        if not res_template.data: raise HTTPException(status_code=500, detail="Failed to save template")
        new_template_id = res_template.data[0]['id']

        slots_data = []
        for slot in request.slots:
            slots_data.append({
                "template_id": new_template_id,
                "slot_type": slot.type,    
                "label_text": slot.content, 
                "data_key": slot.data_key,
                "pos_x": slot.x, "pos_y": slot.y,           
                "width": slot.width, "height": slot.height,
                "style_config": slot.style, "z_index": 1
            })
        if slots_data: execute_supabase(supabase.table("template_slots").insert(slots_data))

        backgrounds_data = []
        if request.backgrounds:
            for bg in request.backgrounds:
                backgrounds_data.append({
                    "template_id": new_template_id,
                    "name": bg.name, "url": bg.url
                })
            execute_supabase(supabase.table("template_backgrounds").insert(backgrounds_data))

        return {"message": "Saved successfully!", "id": new_template_id}
    except Exception as e:
        print("Create Template Error:", e) 
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/templates/{template_id}")
def update_template(template_id: str, request: TemplateCreate):
    try:
        template_data = {
            "name": request.name,
            "base_width": request.width,
            "base_height": request.height,
            "background_url": request.background_url,
            "is_master": request.is_master,
            "owner_id": request.owner_id if hasattr(request, 'owner_id') and request.owner_id else None,
            "updated_at": "now()" 
        }
        execute_supabase(supabase.table("templates").update(template_data).eq("id", template_id))
        
        execute_supabase(supabase.table("template_slots").delete().eq("template_id", template_id))
        execute_supabase(supabase.table("template_backgrounds").delete().eq("template_id", template_id))

        slots_data = []
        for slot in request.slots:
            slots_data.append({
                "template_id": template_id, "slot_type": slot.type,
                "label_text": slot.content, "data_key": slot.data_key,
                "pos_x": slot.x, "pos_y": slot.y,
                "width": slot.width, "height": slot.height,
                "style_config": slot.style, "z_index": 1
            })
        if slots_data: execute_supabase(supabase.table("template_slots").insert(slots_data))

        backgrounds_data = []
        if request.backgrounds:
            for bg in request.backgrounds:
                backgrounds_data.append({
                    "template_id": template_id, "name": bg.name, "url": bg.url
                })
            execute_supabase(supabase.table("template_backgrounds").insert(backgrounds_data))

        return {"message": "Updated successfully!"}
    except Exception as e:
        print("Update Template Error:", e) 
        raise HTTPException(status_code=500, detail=str(e))    

@app.delete("/api/templates/{template_id}")
def delete_template(template_id: str):
    try:
        res = execute_supabase(supabase.table("templates").delete().eq("id", template_id))
        return {"message": "Deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        file_ext = file.filename.split(".")[-1]
        file_path = f"backgrounds/{uuid.uuid4()}.{file_ext}"
        bucket_name = "lotto-assets"
        
        supabase.storage.from_(bucket_name).upload(
            path=file_path, file=file_content,
            file_options={"content-type": file.content_type}
        )
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
        return {"url": public_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# --- Lotteries ---
@app.get("/api/lotteries")
def get_lotteries(search: str = Query(None)):
    try:
        query = supabase.table("lotteries")\
            .select("*, templates(background_url, base_width, base_height)")\
            .eq("is_active", True)
        if search: query = query.ilike("name", f"%{search}%")
        response = execute_supabase(query.order("closing_time", desc=False))
        return response.data
    except Exception as e:
        print("Get Lotteries Error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/lotteries/{lottery_id}")
def get_lottery_details(lottery_id: str, user_id: str = None):
    try:
        # 1. Fetch Lottery
        lottery_res = execute_supabase(supabase.table("lotteries").select("*").eq("id", lottery_id).limit(1))
        if not lottery_res.data: raise HTTPException(status_code=404, detail="Lottery not found")
        lottery = lottery_res.data[0]
        
        target_template_id = None

        # 2. Priority: User Assigned Template
        if user_id:
            try:
                u = execute_supabase(supabase.table("users").select("assigned_template_id").eq("id", user_id).limit(1))
                if u.data and u.data[0].get('assigned_template_id'): 
                    target_template_id = u.data[0]['assigned_template_id']
                
                # 2.1 Auto-Detect Owner
                if not target_template_id:
                    t = execute_supabase(supabase.table("templates").select("id").eq("owner_id", user_id).order("created_at", desc=True).limit(1))
                    if t.data:
                        target_template_id = t.data[0]['id']
            except: pass
        
        # 3. Fallback: Lottery Assigned
        if not target_template_id: target_template_id = lottery.get('template_id')
        
        # 4. Fallback: System Master
        if not target_template_id:
            try:
                l = execute_supabase(supabase.table("templates").select("id").eq("is_active", True).eq("is_master", True).limit(1))
                if l.data: target_template_id = l.data[0]['id']
            except: pass
            
        if not target_template_id: return {"lottery": lottery, "template": None}

        # 5. Fetch Template Detail
        template_res = execute_supabase(supabase.table("templates")\
            .select("*, template_slots(*), template_backgrounds(*)")\
            .eq("id", target_template_id).limit(1))
            
        if not template_res.data: return {"lottery": lottery, "template": None}
        
        return { "lottery": lottery, "template": template_res.data[0], "used_template_id": target_template_id }
    except Exception as e:
        print(f"Get Lottery Details Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/lotteries/{lottery_id}")
def update_lottery(lottery_id: str, request: LotteryUpdate):
    try:
        update_data = {}
        if request.name is not None: update_data["name"] = request.name
        if request.closing_time is not None: update_data["closing_time"] = request.closing_time.isoformat()
        if request.is_active is not None: update_data["is_active"] = request.is_active
        if request.template_id is not None: update_data["template_id"] = request.template_id if request.template_id else None
        
        if update_data: execute_supabase(supabase.table("lotteries").update(update_data).eq("id", lottery_id))
        return {"message": "Updated successfully"}
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
        res = execute_supabase(supabase.table("lotteries").insert(data))
        return {"message": "Created successfully", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/lotteries/{lottery_id}")
def delete_lottery(lottery_id: str):
    try:
        execute_supabase(supabase.table("lotteries").delete().eq("id", lottery_id))
        return {"message": "Deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- User Management ---
@app.post("/api/login")
def login(request: UserLogin):
    try:
        user = execute_supabase(supabase.table("users").select("*").eq("username", request.username).limit(1))
        if not user.data: raise HTTPException(status_code=401, detail="Invalid credentials")
        if not safe_verify_password(request.password, user.data[0]['password']):
             raise HTTPException(status_code=401, detail="Invalid credentials")
        return {k: v for k, v in user.data[0].items() if k != 'password'}
    except Exception as e:
        print(f"Login Error: {e}")
        raise HTTPException(status_code=401, detail="Login failed")

@app.get("/api/users")
def get_users():
    try:
        res = execute_supabase(supabase.table("users").select("*").order("created_at", desc=True))
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{user_id}")
def get_user(user_id: str):
    try:
        res = execute_supabase(supabase.table("users").select("*").eq("id", user_id).limit(1))
        if not res.data: raise HTTPException(status_code=404, detail="User not found")
        return res.data[0]
    except Exception as e:
        print(f"Get User Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users")
def create_user(request: UserCreate):
    try:
        hashed = safe_hash_password(request.password)
        user_data = {
            "username": request.username, "password": hashed,
            "name": request.name, "role": request.role,
            "assigned_template_id": request.assigned_template_id,
            "allowed_template_ids": request.allowed_template_ids,
            "custom_line_id": request.custom_line_id if hasattr(request, 'custom_line_id') else None,
            "custom_qr_code_url": request.custom_qr_code_url if hasattr(request, 'custom_qr_code_url') else None
        }
        execute_supabase(supabase.table("users").insert(user_data))
        return {"message": "User created successfully"}
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=400, detail="Username already exists")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{user_id}")
def update_user(user_id: str, request: UserUpdate):
    try:
        update_data = {}
        if request.name: update_data["name"] = request.name
        if request.password: update_data["password"] = safe_hash_password(request.password)
        if request.assigned_template_id is not None: 
            update_data["assigned_template_id"] = request.assigned_template_id if request.assigned_template_id else None
        if request.allowed_template_ids is not None: 
            update_data["allowed_template_ids"] = request.allowed_template_ids
        
        # Support updating custom config
        if hasattr(request, 'custom_line_id') and request.custom_line_id is not None: 
            update_data["custom_line_id"] = request.custom_line_id
        if hasattr(request, 'custom_qr_code_url') and request.custom_qr_code_url is not None:
            update_data["custom_qr_code_url"] = request.custom_qr_code_url

        if update_data: execute_supabase(supabase.table("users").update(update_data).eq("id", user_id))
        return {"message": "User updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
def delete_user(user_id: str):
    try:
        execute_supabase(supabase.table("users").delete().eq("id", user_id))
        return {"message": "User deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
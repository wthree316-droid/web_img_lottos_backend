from fastapi import APIRouter, HTTPException, Depends
from schemas import UserUpdate
from database import supabase, execute_supabase
from auth_utils import verify_password, get_password_hash, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from schemas import (
    GenerateRequest, GenerateResponse, TemplateCreate, UploadResponse, 
    UserLogin, UserCreate, UserUpdate, GlobalConfigUpdate, GlobalConfigResponse,
    LotteryUpdate, LotteryCreate
)

# สร้าง Router ตั้ง Prefix เป็น /api/users
router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("")
def get_users():
    try:
        res = execute_supabase(supabase.table("users").select("*").order("created_at", desc=True))
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}") 
def get_user(user_id: str):
    try:
        res = execute_supabase(supabase.table("users").select("*").eq("id", user_id).limit(1))
        if not res.data: raise HTTPException(status_code=404, detail="User not found")
        return res.data[0]
    except Exception as e:
        print(f"Get User Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
def create_user(request: UserCreate):
    try:
        hashed = get_password_hash(request.password)
        user_data = {
            "username": request.username, "password": hashed,
            "name": request.name, "role": request.role,
            "assigned_template_id": request.assigned_template_id,
            "allowed_template_ids": request.allowed_template_ids,
            "custom_line_id": request.custom_line_id if hasattr(request, 'custom_line_id') else None,
            "custom_qr_code_url": request.custom_qr_code_url if hasattr(request, 'custom_qr_code_url') else None,
            "is_suspended": request.is_suspended
        }
        execute_supabase(supabase.table("users").insert(user_data))
        return {"message": "User created successfully"}
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=400, detail="Username already exists")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{user_id}") # ✅ เติม / ให้แล้ว
def update_user(user_id: str, request: UserUpdate):
    try:
        update_data = {}
        if request.name: update_data["name"] = request.name
        if request.password: update_data["password"] = get_password_hash(request.password)
        if request.assigned_template_id is not None: 
            update_data["assigned_template_id"] = request.assigned_template_id if request.assigned_template_id else None
        if request.allowed_template_ids is not None: 
            update_data["allowed_template_ids"] = request.allowed_template_ids
        
        # Support updating custom config
        if hasattr(request, 'custom_line_id') and request.custom_line_id is not None: 
            update_data["custom_line_id"] = request.custom_line_id
        if hasattr(request, 'custom_qr_code_url') and request.custom_qr_code_url is not None:
            update_data["custom_qr_code_url"] = request.custom_qr_code_url
            
        if request.is_suspended is not None: 
            update_data["is_suspended"] = request.is_suspended

        if update_data: execute_supabase(supabase.table("users").update(update_data).eq("id", user_id))
        return {"message": "User updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}") # ✅ เติม / ให้แล้ว
def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    # ✅ ตรวจว่าคนที่ยิงมาเป็น Admin หรือเปล่า
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="คุณไม่มีสิทธิ์ใช้งานส่วนนี้")

    try:
        execute_supabase(supabase.table("users").delete().eq("id", user_id))
        return {"message": "User deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
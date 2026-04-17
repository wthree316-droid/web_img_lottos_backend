from fastapi import APIRouter, HTTPException
from schemas import UserLogin, UserCreate
from auth_utils import verify_password, get_password_hash, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from database import supabase, execute_supabase
from datetime import timedelta
import uuid

# สร้าง Router และตั้ง Prefix เป็น /api
router = APIRouter(prefix="/api", tags=["Authentication"])

# --- User Management ---
@router.post("/login")
def login(request: UserLogin):
    try:
        res = execute_supabase(supabase.table("users").select("*").eq("username", request.username).limit(1))
        
        # 1. เช็คว่ามีข้อมูลตอบกลับมาหรือไม่
        if not res.data or len(res.data) == 0: 
            raise HTTPException(status_code=401, detail="ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง")
            
        # 2. ดึงเอา Dictionary ของ User ออกมาจาก List (เพื่อไม่ให้ติด APIResponse)
        user_db = res.data[0]
        # 2.1. เช็คว่าโดนแบนหรือไม่
        if user_db.get("is_suspended"):
            raise HTTPException(status_code=403, detail="บัญชีของคุณถูกระงับการใช้งาน กรุณาติดต่อผู้ดูแลระบบ")
        
        # 3. นำรหัสผ่านที่ได้มาเช็ค
        if not verify_password(request.password, user_db["password"]):
             raise HTTPException(status_code=401, detail="ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง")
        
        # 4. ลบรหัสผ่านทิ้งก่อนส่งกลับไปหน้าเว็บ
        user_data = {k: v for k, v in user_db.items() if k != 'password'}
        
        # ✅ สร้าง JWT Token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_data["username"], "id": user_data["id"], "role": user_data["role"]},
            expires_delta=access_token_expires
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Generate Request ---
class GenerateRequest(BaseModel):
    template_id: str
    user_seed: Optional[str] = None
    slot_configs: List[Dict[str, Any]]
    # ✅ เพิ่ม: ระบุว่ากำลัง Gen ให้ใคร (เพื่อให้ระบบดึง QR/Line ของคนนั้นมาใช้)
    target_user_id: Optional[str] = None 

class GenerateResponse(BaseModel):
    results: Dict[str, str]

# --- Template Schemas ---
class SlotSchema(BaseModel):
    id: Optional[str] # ทำให้ Optional เพราะตอนสร้างใหม่อาจยังไม่มี ID
    type: str
    content: str
    data_key: Optional[str] = ""
    x: float
    y: float
    width: float
    height: float
    style: Dict[str, Any]

class BackgroundSchema(BaseModel):
    name: str
    url: str

class TemplateCreate(BaseModel):
    name: str
    width: int
    height: int
    background_url: Optional[str] = "" 
    backgrounds: Optional[List[BackgroundSchema]] = []
    slots: List[SlotSchema]
    is_master: bool = False
    # ✅ เพิ่ม: ระบุเจ้าของ (ถ้า Admin สร้างให้ User ก็ส่ง ID User มาที่นี่)
    owner_id: Optional[str] = None 

# --- User Schemas ---
class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    name: str
    role: str = "member"
    assigned_template_id: Optional[str] = None
    allowed_template_ids: Optional[List[str]] = []
    # ✅ เพิ่ม: รับค่า Config ตั้งแต่ตอนสร้างได้เลย (Optional)
    custom_line_id: Optional[str] = None
    custom_qr_code_url: Optional[str] = None
    is_suspended: Optional[bool] = False

class UserUpdate(BaseModel):
    password: Optional[str] = None
    name: Optional[str] = None
    assigned_template_id: Optional[str] = None
    allowed_template_ids: Optional[List[str]] = None
    # ✅ เพิ่ม: สำหรับอัปเดต Line/QR ส่วนตัว
    custom_line_id: Optional[str] = None
    custom_qr_code_url: Optional[str] = None
    is_suspended: Optional[bool] = None

class UploadResponse(BaseModel):
    url: str

class GlobalConfigUpdate(BaseModel):
    qr_code_url: Optional[str] = None
    line_id: Optional[str] = None

class GlobalConfigResponse(BaseModel):
    qr_code_url: str
    line_id: str

class LotteryCreate(BaseModel):
    name: str
    template_id: Optional[str] = None
    closing_time: Optional[datetime] = None
    is_active: bool = True
    icon_url: Optional[str] = None

class LotteryUpdate(BaseModel):
    name: Optional[str] = None
    closing_time: Optional[datetime] = None
    is_active: Optional[bool] = None
    template_id: Optional[str] = None
    icon_url: Optional[str] = None
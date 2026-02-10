from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

# สิ่งที่ Frontend ส่งมาขอให้เรา Gen เลข
class GenerateRequest(BaseModel):
    template_id: str
    user_seed: Optional[str] = None  # เลขตั้งต้น 2 ตัว (ถ้ามี) เช่น "85"
    slot_configs: List[Dict[str, Any]] # รายการ Slot จาก DB (เราจะเอา data_key มาดูว่าต้อง Gen อะไรบ้าง)

# สิ่งที่เราจะตอบกลับไป (Key: ค่าที่สุ่มได้)
# ตัวอย่าง: { "digit_3": "851", "digit_2_bottom": "85", "running": "8" }
class GenerateResponse(BaseModel):
    results: Dict[str, str]

class SlotSchema(BaseModel):
    id: str
    type: str # system_label, user_input, auto_data, qr_code, static_text
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
    backgrounds: Optional[List[BackgroundSchema]] = [] # ✅ เพิ่มรายการพื้นหลังทางเลือก
    slots: List[SlotSchema]
    is_master: bool = False

# ✅ เพิ่ม Class นี้สำหรับตอบกลับตอนอัปโหลดเสร็จ
class UploadResponse(BaseModel):
    url: str

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
    allowed_template_ids: Optional[List[str]] = [] # ✅ เพิ่มฟิลด์

class UserUpdate(BaseModel):
    password: Optional[str] = None
    name: Optional[str] = None
    assigned_template_id: Optional[str] = None
    allowed_template_ids: Optional[List[str]] = None # ✅ เพิ่มฟิลด์

# --- Global Config Schemas ---
class GlobalConfigUpdate(BaseModel):
    qr_code_url: Optional[str] = None
    line_id: Optional[str] = None

class GlobalConfigResponse(BaseModel):
    qr_code_url: str
    line_id: str

# --- Lottery Schemas ---
class LotteryCreate(BaseModel):
    name: str
    template_id: Optional[str] = None
    closing_time: Optional[datetime] = None
    is_active: bool = True

class LotteryUpdate(BaseModel):
    name: Optional[str] = None # ✅ เพิ่ม name
    closing_time: Optional[datetime] = None
    is_active: Optional[bool] = None
    template_id: Optional[str] = None

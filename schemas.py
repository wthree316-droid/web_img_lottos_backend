from pydantic import BaseModel
from typing import List, Optional, Dict, Any

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
    type: str # system_label, user_input, auto_data
    content: str
    data_key: Optional[str] = ""
    x: float
    y: float
    width: float
    height: float
    style: Dict[str, Any]

class TemplateCreate(BaseModel):
    name: str
    width: int
    height: int
    background_url: Optional[str] = "" # ✅ เพิ่มบรรทัดนี้ครับ!
    slots: List[SlotSchema]

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

class UserUpdate(BaseModel):
    password: Optional[str] = None
    name: Optional[str] = None
    assigned_template_id: Optional[str] = None
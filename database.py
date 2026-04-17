import os
from supabase import create_client, Client
from dotenv import load_dotenv
from fastapi import HTTPException
import time
import random

# โหลดค่าจาก .env
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Supabase credentials not found in .env file")

# สร้างตัวเชื่อมต่อ (Client)
supabase: Client = create_client(url, key)

print("✅ Supabase Connected Successfully!")

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
            err_str = str(e).lower()
            
            # ✅ เพิ่มคำว่า "streamreset" และ "remote_reset" เข้าไป เพื่อให้มันยิงใหม่เวลา Supabase ตัดสาย
            if "10035" in err_str or "socket" in err_str or "ssl" in err_str or "streamreset" in err_str or "remote_reset" in err_str:
                time.sleep(0.2 + (random.random() * 0.3)) # รอ 0.2 - 0.5 วินาที
                continue
            raise e # ถ้าเป็น Error อื่น (เช่น SQL ผิด) ให้โยนทิ้งเลย
            
    raise last_error

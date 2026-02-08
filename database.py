import os
from supabase import create_client, Client
from dotenv import load_dotenv

# โหลดค่าจาก .env
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Supabase credentials not found in .env file")

# สร้างตัวเชื่อมต่อ (Client)
supabase: Client = create_client(url, key)

print("✅ Supabase Connected Successfully!")
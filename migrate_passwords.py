# Migration Script: Hash existing plain-text passwords in the database
# ⚠️ รันสคริปต์นี้ครั้งเดียวหลังจาก deploy โค้ดใหม่แล้ว

# ขั้นตอนการใช้งาน:
# 1. ตรวจสอบว่าตั้งค่า .env ถูกต้อง (SUPABASE_URL, SUPABASE_KEY)
# 2. รันคำสั่ง: python migrate_passwords.py
# 3. สคริปต์จะ hash password ทุกตัวที่ยังเป็น plain text 

from database import supabase
from passlib.context import CryptContext
import sys
import hashlib
import bcrypt

def is_hashed(password: str) -> bool:
    """เช็คว่า password เป็น bcrypt hash หรือยัง"""
    return password.startswith("$2b$") or password.startswith("$2a$")

def safe_hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')
    # กรณีพิเศษถ้า password ยาวเกิน 72 bytes ตาม logic เดิมของคุณ
    if len(password_bytes) > 72:
        import hashlib
        password = hashlib.sha256(password_bytes).hexdigest()
    
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def migrate_passwords():
    """แปลง plain text passwords เป็น hashed passwords"""
    print("🔍 กำลังค้นหา users ที่มี plain text password...")
    
    try:
        # ดึง users ทั้งหมด
        response = supabase.table("users").select("*").execute()
        users = response.data
        
        if not users:
            print("❌ ไม่พบ users ในระบบ")
            return
        
        print(f"✅ พบ {len(users)} users")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for user in users:
            user_id = user['id']
            username = user['username']
            password = user['password']
            
            try:
                # เช็คว่า hash แล้วหรือยัง
                if is_hashed(password):
                    print(f"⏭️  {username}: Password ถูก hash แล้ว (ข้าม)")
                    skipped_count += 1
                    continue
                
                # ตรวจสอบความยาว password
                password_bytes = password.encode('utf-8')
                if len(password_bytes) > 72:
                    print(f"⚠️  {username}: Password ยาว {len(password_bytes)} bytes (เกิน 72) - จะใช้ SHA256+bcrypt")
                
                # Hash password
                hashed_password = safe_hash_password(password)
                
                # Update ใน database
                supabase.table("users").update({
                    "password": hashed_password
                }).eq("id", user_id).execute()
                
                print(f"✅ {username}: Password ถูก hash เรียบร้อย")
                updated_count += 1
                
            except Exception as user_error:
                print(f"❌ {username}: เกิดข้อผิดพลาด - {str(user_error)}")
                error_count += 1
                continue
        
        print("\n" + "="*50)
        print(f"🎉 Migration เสร็จสิ้น!")
        print(f"   - อัพเดต: {updated_count} users")
        print(f"   - ข้าม: {skipped_count} users (hash อยู่แล้ว)")
        if error_count > 0:
            print(f"   - ❌ ล้มเหลว: {error_count} users")
        print("="*50)
        
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดร้ายแรง: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("="*50)
    print("🔐 Password Migration Script")
    print("="*50)
    
    confirm = input("\n⚠️  คำเตือน: สคริปต์นี้จะแก้ไข passwords ใน database\nต้องการดำเนินการต่อหรือไม่? (yes/no): ")
    
    if confirm.lower() not in ['yes', 'y']:
        print("❌ ยกเลิกการทำงาน")
        sys.exit(0)
    
    migrate_passwords()

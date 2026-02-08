import secrets

class LotteryLogic:
    def __init__(self, seed: str = None):
        self.seed = seed
        # สร้าง "ถังเลขวิน" (Win Pool) เตรียมไว้เลย 1 ชุด สำหรับรอบนี้
        self.win_pool = self._create_win_pool()

    def _create_win_pool(self) -> list:
        """
        สร้างกลุ่มเลขวิน 6 ตัว (Master Set)
        โดยยึดเลข Seed เป็นหลัก แล้วสุ่มเลขอื่นมาเติมให้ครบ
        """
        pool = set()
        
        # 1. เอาเลข Seed ใส่เข้าไปก่อน (ถ้ามี)
        if self.seed:
            for char in self.seed:
                if char.isdigit():
                    pool.add(char)
        
        # 2. สุ่มเลขอื่นมาเติมให้ครบ 6 ตัว (ไม่ให้ซ้ำในถัง)
        all_digits = list('0123456789')
        while len(pool) < 6:
            pool.add(str(secrets.choice(all_digits)))
            
        # แปลงเป็น List แล้วสลับตำแหน่งให้เนียน
        pool_list = list(pool)
        secrets.SystemRandom().shuffle(pool_list)
        return pool_list

    def generate(self, key_type: str) -> str:
        """
        ฟังก์ชันตัดสินใจว่าจะคืนค่าเลขอะไรตาม key_type
        โดยหยิบวัตถุดิบมาจาก self.win_pool
        """
        
        if key_type == "win":
            # คืนค่าเลขวินทั้งดุ้น (เช่น "8-5-1-2-9-0")
            return "-".join(self.win_pool)

        elif key_type == "digit_3":
            # หยิบ 3 ตัวจากถังวิน มาเรียงกัน
            picks = secrets.SystemRandom().sample(self.win_pool, 3)
            return "".join(picks)

        elif key_type == "digit_2_top":
            # หยิบ 2 ตัวจากถังวิน
            picks = secrets.SystemRandom().sample(self.win_pool, 2)
            return "".join(picks)

        elif key_type == "digit_2_bottom":
            # หยิบ 2 ตัวจากถังวิน (สุ่มใหม่ อาจซ้ำกับ top ได้ เพราะเป็น random selection แยกกัน)
            picks = secrets.SystemRandom().sample(self.win_pool, 2)
            return "".join(picks)

        elif key_type == "running":
            # หยิบ 1 ตัวจากถังวิน
            return secrets.choice(self.win_pool)
            
        else:
            # กรณีอื่นๆ สุ่มเลข 2 หัก (00-99)
            return str(secrets.randbelow(100)).zfill(2)
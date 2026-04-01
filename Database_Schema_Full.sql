-- ============================================
-- 🎰 LOTTERY GENERATOR DATABASE SCHEMA (FULL)
-- Version: 4.0 (Upgrade: Multi-style, Global Assets, Closing Time)
-- Compatible with: PostgreSQL 14+ (Supabase)
-- ============================================

-- ⚠️ คำเตือน: สคริปต์นี้ออกแบบมาให้รันซ้ำได้ (Idempotent) 
-- แต่ถ้าต้องการล้างข้อมูลเก่าทั้งหมด ให้ Uncomment บรรทัดข้างล่างนี้:
-- DROP TABLE IF EXISTS global_configs, template_backgrounds, users, lotteries, template_slots, templates CASCADE;
-- DROP TYPE IF EXISTS slot_type_enum;

-- ============================================
-- 1. SETUP ENUMS & TABLES
-- ============================================

-- 1.1 สร้าง ENUM สำหรับประเภทของ Slot (อัปเดตให้รองรับ qr_code และ static_text)
DO $$ BEGIN
    CREATE TYPE slot_type_enum AS ENUM ('system_label', 'user_input', 'auto_data', 'qr_code', 'static_text');
EXCEPTION
    WHEN duplicate_object THEN 
        -- ถ้ามีอยู่แล้ว ให้เพิ่มค่า enum ใหม่เข้าไป
        ALTER TYPE slot_type_enum ADD VALUE IF NOT EXISTS 'qr_code';
        ALTER TYPE slot_type_enum ADD VALUE IF NOT EXISTS 'static_text';
END $$;

-- 1.2 สร้างตารางแม่พิมพ์ (Templates) - เพิ่ม is_master
CREATE TABLE IF NOT EXISTS templates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    base_width INT NOT NULL DEFAULT 1080,
    base_height INT NOT NULL DEFAULT 1920,
    background_url TEXT, -- รูปหลัก (Default)
    is_master BOOLEAN DEFAULT FALSE, -- ✅ เป็นแม่พิมพ์หลักหรือไม่
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 1.3 สร้างตารางรูปพื้นหลังเพิ่มเติม (Template Backgrounds) - ✅ ตารางใหม่
CREATE TABLE IF NOT EXISTS template_backgrounds (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,
    name TEXT NOT NULL, -- ชื่อสไตล์ เช่น "สีแดงตรุษจีน", "สีเขียวเหนี่ยวทรัพย์"
    url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 1.4 สร้างตารางค่ากลาง (Global Configs) - ✅ ตารางใหม่
CREATE TABLE IF NOT EXISTS global_configs (
    key TEXT PRIMARY KEY, -- เช่น 'qr_code_url', 'line_id'
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 1.5 สร้างตารางกล่องข้อมูล (Slots)
CREATE TABLE IF NOT EXISTS template_slots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,
    slot_type slot_type_enum NOT NULL,
    data_key TEXT,
    label_text TEXT,
    pos_x FLOAT NOT NULL DEFAULT 0,
    pos_y FLOAT NOT NULL DEFAULT 0,
    width FLOAT NOT NULL DEFAULT 20,
    height FLOAT NOT NULL DEFAULT 10,
    style_config JSONB DEFAULT '{}'::JSONB,
    z_index INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 1.6 สร้างตารางรายชื่อหวย (เพิ่ม closing_time)
CREATE TABLE IF NOT EXISTS lotteries (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    template_id UUID REFERENCES templates(id) ON DELETE SET NULL,
    closing_time TIMESTAMPTZ, -- ✅ เวลาปิดรับ (เช่น 15:30 ของทุกวัน)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$ 
BEGIN 
    -- เพิ่ม column closing_time ถ้ายังไม่มี
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'lotteries' AND column_name = 'closing_time') THEN
        ALTER TABLE lotteries ADD COLUMN closing_time TIMESTAMPTZ;
    END IF;
END $$;

-- 1.7 สร้างตาราง Users
CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT,
    role TEXT DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    assigned_template_id UUID REFERENCES templates(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 2. INDEXES & TRIGGERS
-- ============================================

CREATE INDEX IF NOT EXISTS idx_template_slots_template_id ON template_slots(template_id);
CREATE INDEX IF NOT EXISTS idx_template_backgrounds_template_id ON template_backgrounds(template_id);
CREATE INDEX IF NOT EXISTS idx_lotteries_template_id ON lotteries(template_id);
CREATE INDEX IF NOT EXISTS idx_users_assigned_template_id ON users(assigned_template_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_lotteries_closing_time ON lotteries(closing_time);

-- Function สำหรับ update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_templates_updated_at ON templates;
CREATE TRIGGER update_templates_updated_at 
BEFORE UPDATE ON templates
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_global_configs_updated_at ON global_configs;
CREATE TRIGGER update_global_configs_updated_at 
BEFORE UPDATE ON global_configs
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 3. ROW LEVEL SECURITY (RLS)
-- ============================================

ALTER TABLE templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_backgrounds ENABLE ROW LEVEL SECURITY;
ALTER TABLE global_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE lotteries ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- เคลียร์ Policy เก่า
DROP POLICY IF EXISTS "Admins have full access to templates" ON templates;
DROP POLICY IF EXISTS "Members can read templates" ON templates;
DROP POLICY IF EXISTS "All authenticated users can read template_slots" ON template_slots;
DROP POLICY IF EXISTS "All users can read active lotteries" ON lotteries;
DROP POLICY IF EXISTS "Only admins can access users" ON users;
DROP POLICY IF EXISTS "Admins have full access to backgrounds" ON template_backgrounds;
DROP POLICY IF EXISTS "Members can read backgrounds" ON template_backgrounds;
DROP POLICY IF EXISTS "Admins can manage global configs" ON global_configs;
DROP POLICY IF EXISTS "Everyone can read global configs" ON global_configs;

-- สร้าง Policy ใหม่
CREATE POLICY "Admins have full access to templates" ON templates FOR ALL 
USING (EXISTS (SELECT 1 FROM users WHERE users.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND users.role = 'admin'));

CREATE POLICY "Members can read templates" ON templates FOR SELECT 
USING (EXISTS (SELECT 1 FROM users WHERE users.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND users.role IN ('admin', 'member')));

CREATE POLICY "Admins have full access to backgrounds" ON template_backgrounds FOR ALL 
USING (EXISTS (SELECT 1 FROM users WHERE users.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND users.role = 'admin'));

CREATE POLICY "Members can read backgrounds" ON template_backgrounds FOR SELECT 
USING (true);

CREATE POLICY "Admins can manage global configs" ON global_configs FOR ALL 
USING (EXISTS (SELECT 1 FROM users WHERE users.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND users.role = 'admin'));

CREATE POLICY "Everyone can read global configs" ON global_configs FOR SELECT USING (true);

CREATE POLICY "All authenticated users can read template_slots" ON template_slots FOR SELECT USING (true);
CREATE POLICY "All users can read active lotteries" ON lotteries FOR SELECT USING (is_active = true);

CREATE POLICY "Only admins can access users" ON users FOR ALL 
USING (EXISTS (SELECT 1 FROM users u WHERE u.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND u.role = 'admin'));

-- ============================================
-- 4. SEED DATA (ข้อมูลเริ่มต้น)
-- ============================================

-- 4.1 สร้าง Admin (ถ้ายังไม่มี)
INSERT INTO users (username, password, name, role)
VALUES ('admin', '1234', 'Admin สูงสุด', 'admin')
ON CONFLICT (username) DO NOTHING;

-- 4.2 สร้างค่ากลางเริ่มต้น (Global Configs)
INSERT INTO global_configs (key, value, description) VALUES
('qr_code_url', '', 'URL ของรูป QR Code กลาง'),
('line_id', '@lotto', 'LINE ID สำหรับติดต่อ')
ON CONFLICT (key) DO NOTHING;

-- 4.3 เพิ่มรายชื่อหวย (ใช้ ON CONFLICT DO NOTHING เพื่อกันซ้ำ)

-- ==========================================
-- 1. หมวดหวยไทย (THAI)
-- ==========================================
INSERT INTO lotteries (name, template_id) SELECT 'รัฐบาลไทย', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'รัฐบาลไทย 70', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ออมสิน', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ธกส', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;

-- ==========================================
-- 2. หมวดหวยลาว (LAOS)
-- ==========================================
INSERT INTO lotteries (name, template_id) SELECT 'ลาวประตูชัย', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาวสันติภาพ', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ประชาชนลาว', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาว Extra', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาว TV', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาว HD', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาวสตาร์', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'หุ้นลาว VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาวพัฒนา', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'หวยลาวสามัคคี', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาวพัฒนา 70', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาวอาเซียน', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาวสามัคคี VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาว VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาวSTAR VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ลาว กาชาด', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;

-- ==========================================
-- 3. หมวดหวยฮานอย (HANOI)
-- ==========================================
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอยอาเซียน', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'เวียดนาม VIP เช้า', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอย HD', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอย สตาร์', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'เวียดนาม VIP บ่าย', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอย TV', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอย กาชาด', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอยเฉพาะกิจ', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'เวียดนาม VIP เย็น', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอยสามัคคี', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอยพิเศษ', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอยปกติ', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอยตรุษจีน', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอยพัฒนา', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอย VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอย 4D', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอย EXTRA', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮานอยดึก', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;

-- ==========================================
-- 4. หมวดหวยหุ้น (STOCKS)
-- ==========================================
INSERT INTO lotteries (name, template_id) SELECT 'ดาวโจนส์ USA', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ดาวโจนส์', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'นิเคอิ เช้า', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'จีน เช้า', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮั่งเส็ง เช้า', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ไต้หวัน', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'เกาหลี', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'นิเคอิ บ่าย', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'จีน บ่าย', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮั่งเส็ง บ่าย', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ไทยเย็น', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'สิงคโปร์', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'อินเดีย', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'อิยิปต์', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'มาเลเซีย', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'อังกฤษ', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'เยอรมัน', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'รัสเซีย', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ยูโร', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;

-- ==========================================
-- 5. หมวดหวยหุ้น VIP (STOCKSVIP)
-- ==========================================
INSERT INTO lotteries (name, template_id) SELECT 'ดาวโจนส์ VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ดาวโจนส์ STAR', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ดาวโจนส์ Mid Night', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ดาวโจนส์ Extra', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ดาวโจนส์ TV', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'นิเคอิเช้า VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'จีนเช้า VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮั่งเส็งเช้า VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ไต้หวัน VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'เกาหลี VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'นิเคอิบ่าย VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'จีนบ่าย VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'ฮั่งเส็งบ่าย VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'สิงคโปร์ VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'อินเดีย VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'อังกฤษ VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'เยอรมัน VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'รัสเซีย VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;

-- ==========================================
-- 6. หมวดอื่นๆ (OTHERS) - แม่โขง
-- ==========================================
INSERT INTO lotteries (name, template_id) SELECT 'แม่โขงทูเดย์', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'แม่โขง HD', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'แม่โขงเมก้า', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'แม่โขงสตาร์', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'แม่โขงพลัส', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'แม่โขงพิเศษ', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'แม่โขงปกติ', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'แม่โขง VIP', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'แม่โขงพัฒนา', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'แม่โขงโกลด์', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;
INSERT INTO lotteries (name, template_id) SELECT 'แม่โขงไนท์', id FROM templates LIMIT 1 ON CONFLICT (name) DO NOTHING;

-- ============================================
-- 5. VIEWS & COMMENTS
-- ============================================

CREATE OR REPLACE VIEW template_usage AS
SELECT 
    t.id as template_id,
    t.name as template_name,
    COUNT(DISTINCT l.id) as lottery_count,
    COUNT(DISTINCT u.id) as user_count
FROM templates t
LEFT JOIN lotteries l ON l.template_id = t.id
LEFT JOIN users u ON u.assigned_template_id = t.id
GROUP BY t.id, t.name;

COMMENT ON TABLE templates IS 'แม่พิมพ์หวย - เก็บ layout และ background หลัก';
COMMENT ON TABLE template_backgrounds IS 'เก็บรูปพื้นหลังทางเลือกสำหรับแม่พิมพ์ (Multi-style)';
COMMENT ON TABLE global_configs IS 'เก็บค่ากลางของระบบ เช่น QR Code, Line ID';
COMMENT ON TABLE template_slots IS 'กล่องข้อมูลภายในแม่พิมพ์';
COMMENT ON TABLE lotteries IS 'รายชื่อหวยทั้งหมดในระบบ พร้อมเวลาปิดรับ';
COMMENT ON TABLE users IS 'ผู้ใช้ระบบ (Admin/Member) - Password เก็บเป็น bcrypt hash';

-- ✅ DONE!

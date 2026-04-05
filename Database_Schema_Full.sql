-- ============================================
-- 🎰 LOTTERY GENERATOR DATABASE SCHEMA (ULTIMATE FULL VERSION)
-- Compatible with: PostgreSQL 14+ (Supabase)
-- รวมฟีเจอร์: Multi-style, Global Assets, Closing Time, Personal Templates, QR/Line Configs
-- ============================================

-- ============================================
-- 1. SETUP ENUMS
-- ============================================

-- 1.1 สร้าง ENUM สำหรับประเภทของ Slot
DO $$ BEGIN
    CREATE TYPE slot_type_enum AS ENUM ('system_label', 'user_input', 'auto_data', 'qr_code', 'static_text');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- เพื่อความชัวร์ (เผื่อมี enum เก่าอยู่ ให้เพิ่มค่าใหม่เข้าไป)
ALTER TYPE slot_type_enum ADD VALUE IF NOT EXISTS 'qr_code';
ALTER TYPE slot_type_enum ADD VALUE IF NOT EXISTS 'static_text';

-- ============================================
-- 2. SETUP TABLES (สร้างตารางหลัก)
-- ============================================

-- 2.1 สร้างตาราง Users ก่อน (เพื่อเอาไว้ผูกเป็นเจ้าของแม่พิมพ์)
CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT,
    role TEXT DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    allowed_template_ids JSONB DEFAULT '[]'::JSONB, -- เก็บรายชื่อแม่พิมพ์ที่อนุญาต
    custom_line_id TEXT,                            -- Line ID ส่วนตัว
    custom_qr_code_url TEXT,                        -- รูป QR Code ส่วนตัว
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.2 สร้างตารางแม่พิมพ์ (Templates)
CREATE TABLE IF NOT EXISTS templates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    base_width INT NOT NULL DEFAULT 1080,
    base_height INT NOT NULL DEFAULT 1920,
    background_url TEXT,
    is_master BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    owner_id UUID REFERENCES users(id) ON DELETE CASCADE, -- ผูกเจ้าของแม่พิมพ์
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.3 กลับไปเพิ่ม Foreign Key ให้ Users (ผูกแม่พิมพ์เริ่มต้น)
DO $$ BEGIN
    ALTER TABLE users ADD COLUMN assigned_template_id UUID REFERENCES templates(id) ON DELETE SET NULL;
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

-- 2.4 สร้างตารางรูปพื้นหลังเพิ่มเติม (Template Backgrounds)
CREATE TABLE IF NOT EXISTS template_backgrounds (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.5 สร้างตารางค่ากลาง (Global Configs)
CREATE TABLE IF NOT EXISTS global_configs (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.6 สร้างตารางกล่องข้อมูล (Slots)
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

-- 2.7 สร้างตารางรายชื่อหวย
CREATE TABLE IF NOT EXISTS lotteries (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    template_id UUID REFERENCES templates(id) ON DELETE SET NULL,
    closing_time TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 3. INDEXES & TRIGGERS (เพิ่มความเร็วการค้นหา)
-- ============================================

CREATE INDEX IF NOT EXISTS idx_template_slots_template_id ON template_slots(template_id);
CREATE INDEX IF NOT EXISTS idx_template_backgrounds_template_id ON template_backgrounds(template_id);
CREATE INDEX IF NOT EXISTS idx_lotteries_template_id ON lotteries(template_id);
CREATE INDEX IF NOT EXISTS idx_users_assigned_template_id ON users(assigned_template_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_lotteries_closing_time ON lotteries(closing_time);
CREATE INDEX IF NOT EXISTS idx_templates_owner_id ON templates(owner_id);

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
-- 4. ROW LEVEL SECURITY (RLS)
-- ============================================

ALTER TABLE templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_backgrounds ENABLE ROW LEVEL SECURITY;
ALTER TABLE global_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE lotteries ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- เคลียร์ Policy เก่าทิ้งทั้งหมด เพื่อลง Policy ใหม่ที่อัปเดตแล้ว
DROP POLICY IF EXISTS "Admins have full access to templates" ON templates;
DROP POLICY IF EXISTS "Members can read templates" ON templates;
DROP POLICY IF EXISTS "Members can read system and own templates" ON templates;
DROP POLICY IF EXISTS "Members manage own templates" ON templates;
DROP POLICY IF EXISTS "All authenticated users can read template_slots" ON template_slots;
DROP POLICY IF EXISTS "All users can read active lotteries" ON lotteries;
DROP POLICY IF EXISTS "Only admins can access users" ON users;
DROP POLICY IF EXISTS "Admins have full access to backgrounds" ON template_backgrounds;
DROP POLICY IF EXISTS "Members can read backgrounds" ON template_backgrounds;
DROP POLICY IF EXISTS "Admins can manage global configs" ON global_configs;
DROP POLICY IF EXISTS "Everyone can read global configs" ON global_configs;

-- 🛡️ POLICIES สำหรับ Users
CREATE POLICY "Only admins can access users" ON users FOR ALL 
USING (EXISTS (SELECT 1 FROM users u WHERE u.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND u.role = 'admin'));

-- 🛡️ POLICIES สำหรับ Templates
CREATE POLICY "Admins have full access to templates" ON templates FOR ALL 
USING (EXISTS (SELECT 1 FROM users WHERE users.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND users.role = 'admin'));

CREATE POLICY "Members can read system and own templates" ON templates FOR SELECT 
USING (owner_id IS NULL OR owner_id::text = (current_setting('request.jwt.claims', true)::json->>'sub'));

CREATE POLICY "Members manage own templates" ON templates FOR ALL
USING (owner_id::text = (current_setting('request.jwt.claims', true)::json->>'sub'));

-- 🛡️ POLICIES สำหรับ Backgrounds
CREATE POLICY "Admins have full access to backgrounds" ON template_backgrounds FOR ALL 
USING (EXISTS (SELECT 1 FROM users WHERE users.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND users.role = 'admin'));

CREATE POLICY "Members can read backgrounds" ON template_backgrounds FOR SELECT USING (true);

-- 🛡️ POLICIES สำหรับ Global Configs
CREATE POLICY "Admins can manage global configs" ON global_configs FOR ALL 
USING (EXISTS (SELECT 1 FROM users WHERE users.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND users.role = 'admin'));

CREATE POLICY "Everyone can read global configs" ON global_configs FOR SELECT USING (true);

-- 🛡️ POLICIES สำหรับ Slots & Lotteries
CREATE POLICY "All authenticated users can read template_slots" ON template_slots FOR SELECT USING (true);
CREATE POLICY "All users can read active lotteries" ON lotteries FOR SELECT USING (is_active = true);


-- ============================================
-- 5. SEED DATA (ข้อมูลตัวอย่างเริ่มต้น)
-- ============================================

-- 5.1 สร้าง Admin (username: admin, password: 1234)
INSERT INTO users (username, password, name, role)
VALUES ('admin', '1234', 'Admin สูงสุด', 'admin')
ON CONFLICT (username) DO NOTHING;

-- 5.2 สร้างค่ากลางเริ่มต้น
INSERT INTO global_configs (key, value, description) VALUES
('qr_code_url', '', 'URL ของรูป QR Code กลาง'),
('line_id', '@lotto', 'LINE ID สำหรับติดต่อ')
ON CONFLICT (key) DO NOTHING;

-- 5.3 เพิ่มรายชื่อหวย (ถ้ามีแล้วจะไม่ซ้ำ)
INSERT INTO lotteries (name) VALUES 
('รัฐบาลไทย'), ('รัฐบาลไทย 70'), ('ออมสิน'), ('ธกส'),
('ลาวประตูชัย'), ('ลาวสันติภาพ'), ('ประชาชนลาว'), ('ลาว Extra'), ('ลาว TV'), ('ลาว HD'), ('ลาวสตาร์'), ('หุ้นลาว VIP'), ('ลาวพัฒนา'), ('หวยลาวสามัคคี'), ('ลาวพัฒนา 70'), ('ลาวอาเซียน'), ('ลาวสามัคคี VIP'), ('ลาว VIP'), ('ลาวSTAR VIP'), ('ลาว กาชาด'),
('ฮานอยอาเซียน'), ('เวียดนาม VIP เช้า'), ('ฮานอย HD'), ('ฮานอย สตาร์'), ('เวียดนาม VIP บ่าย'), ('ฮานอย TV'), ('ฮานอย กาชาด'), ('ฮานอยเฉพาะกิจ'), ('เวียดนาม VIP เย็น'), ('ฮานอยสามัคคี'), ('ฮานอยพิเศษ'), ('ฮานอยปกติ'), ('ฮานอยตรุษจีน'), ('ฮานอยพัฒนา'), ('ฮานอย VIP'), ('ฮานอย 4D'), ('ฮานอย EXTRA'), ('ฮานอยดึก'),
('ดาวโจนส์ USA'), ('ดาวโจนส์'), ('นิเคอิ เช้า'), ('จีน เช้า'), ('ฮั่งเส็ง เช้า'), ('ไต้หวัน'), ('เกาหลี'), ('นิเคอิ บ่าย'), ('จีน บ่าย'), ('ฮั่งเส็ง บ่าย'), ('ไทยเย็น'), ('สิงคโปร์'), ('อินเดีย'), ('อิยิปต์'), ('มาเลเซีย'), ('อังกฤษ'), ('เยอรมัน'), ('รัสเซีย'), ('ยูโร'),
('ดาวโจนส์ VIP'), ('ดาวโจนส์ STAR'), ('ดาวโจนส์ Mid Night'), ('ดาวโจนส์ Extra'), ('ดาวโจนส์ TV'), ('นิเคอิเช้า VIP'), ('จีนเช้า VIP'), ('ฮั่งเส็งเช้า VIP'), ('ไต้หวัน VIP'), ('เกาหลี VIP'), ('นิเคอิบ่าย VIP'), ('จีนบ่าย VIP'), ('ฮั่งเส็งบ่าย VIP'), ('สิงคโปร์ VIP'), ('อินเดีย VIP'), ('อังกฤษ VIP'), ('เยอรมัน VIP'), ('รัสเซีย VIP'),
('แม่โขงทูเดย์'), ('แม่โขง HD'), ('แม่โขงเมก้า'), ('แม่โขงสตาร์'), ('แม่โขงพลัส'), ('แม่โขงพิเศษ'), ('แม่โขงปกติ'), ('แม่โขง VIP'), ('แม่โขงพัฒนา'), ('แม่โขงโกลด์'), ('แม่โขงไนท์')
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- 6. VIEWS & COMMENTS
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
COMMENT ON TABLE users IS 'ผู้ใช้ระบบ (Admin/Member)';

-- 🔥 แจ้งเตือน Supabase ให้โหลด Schema ใหม่ (เพื่อให้ API อัปเดตทันที)
NOTIFY pgrst, 'reload config';
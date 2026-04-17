-- ============================================
-- 📁 ไฟล์ที่ 1: โครงสร้างฐานข้อมูลหลัก (Schema & RLS)
-- ============================================

-- 1. SETUP ENUMS
DO $$ BEGIN
    CREATE TYPE slot_type_enum AS ENUM ('system_label', 'user_input', 'auto_data', 'qr_code', 'static_text');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
ALTER TYPE slot_type_enum ADD VALUE IF NOT EXISTS 'qr_code';
ALTER TYPE slot_type_enum ADD VALUE IF NOT EXISTS 'static_text';

-- 2. SETUP TABLES
CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT,
    role TEXT DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    allowed_template_ids JSONB DEFAULT '[]'::JSONB,
    custom_line_id TEXT,
    custom_qr_code_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS templates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    base_width INT NOT NULL DEFAULT 1080,
    base_height INT NOT NULL DEFAULT 1920,
    background_url TEXT,
    is_master BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$ BEGIN
    ALTER TABLE users ADD COLUMN assigned_template_id UUID REFERENCES templates(id) ON DELETE SET NULL;
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS template_backgrounds (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS global_configs (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS lotteries (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    template_id UUID REFERENCES templates(id) ON DELETE SET NULL,
    closing_time TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. INDEXES & TRIGGERS
CREATE INDEX IF NOT EXISTS idx_template_slots_template_id ON template_slots(template_id);
CREATE INDEX IF NOT EXISTS idx_template_backgrounds_template_id ON template_backgrounds(template_id);
CREATE INDEX IF NOT EXISTS idx_lotteries_template_id ON lotteries(template_id);
CREATE INDEX IF NOT EXISTS idx_users_assigned_template_id ON users(assigned_template_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_lotteries_closing_time ON lotteries(closing_time);
CREATE INDEX IF NOT EXISTS idx_templates_owner_id ON templates(owner_id);

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

-- 4. ROW LEVEL SECURITY (RLS)
ALTER TABLE templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_backgrounds ENABLE ROW LEVEL SECURITY;
ALTER TABLE global_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE lotteries ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

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

CREATE POLICY "Only admins can access users" ON users FOR ALL USING (EXISTS (SELECT 1 FROM users u WHERE u.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND u.role = 'admin'));
CREATE POLICY "Admins have full access to templates" ON templates FOR ALL USING (EXISTS (SELECT 1 FROM users WHERE users.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND users.role = 'admin'));
CREATE POLICY "Members can read system and own templates" ON templates FOR SELECT USING (owner_id IS NULL OR owner_id::text = (current_setting('request.jwt.claims', true)::json->>'sub'));
CREATE POLICY "Members manage own templates" ON templates FOR ALL USING (owner_id::text = (current_setting('request.jwt.claims', true)::json->>'sub'));
CREATE POLICY "Admins have full access to backgrounds" ON template_backgrounds FOR ALL USING (EXISTS (SELECT 1 FROM users WHERE users.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND users.role = 'admin'));
CREATE POLICY "Members can read backgrounds" ON template_backgrounds FOR SELECT USING (true);
CREATE POLICY "Admins can manage global configs" ON global_configs FOR ALL USING (EXISTS (SELECT 1 FROM users WHERE users.id::text = (current_setting('request.jwt.claims', true)::json->>'sub') AND users.role = 'admin'));
CREATE POLICY "Everyone can read global configs" ON global_configs FOR SELECT USING (true);
CREATE POLICY "All authenticated users can read template_slots" ON template_slots FOR SELECT USING (true);
CREATE POLICY "All users can read active lotteries" ON lotteries FOR SELECT USING (is_active = true);

-- 5. ESSENTIAL SEED DATA
INSERT INTO users (username, password, name, role) VALUES ('admin', '1234', 'Admin สูงสุด', 'admin') ON CONFLICT (username) DO NOTHING;
INSERT INTO global_configs (key, value, description) VALUES ('qr_code_url', '', 'URL ของรูป QR Code กลาง'), ('line_id', '@lotto', 'LINE ID สำหรับติดต่อ') ON CONFLICT (key) DO NOTHING;

-- 6. VIEWS & COMMENTS
CREATE OR REPLACE VIEW template_usage AS
SELECT t.id as template_id, t.name as template_name, COUNT(DISTINCT l.id) as lottery_count, COUNT(DISTINCT u.id) as user_count
FROM templates t LEFT JOIN lotteries l ON l.template_id = t.id LEFT JOIN users u ON u.assigned_template_id = t.id GROUP BY t.id, t.name;

COMMENT ON TABLE templates IS 'แม่พิมพ์หวย - เก็บ layout และ background หลัก';
COMMENT ON TABLE template_backgrounds IS 'เก็บรูปพื้นหลังทางเลือกสำหรับแม่พิมพ์ (Multi-style)';
COMMENT ON TABLE global_configs IS 'เก็บค่ากลางของระบบ เช่น QR Code, Line ID';
COMMENT ON TABLE template_slots IS 'กล่องข้อมูลภายในแม่พิมพ์';
COMMENT ON TABLE lotteries IS 'รายชื่อหวยทั้งหมดในระบบ พร้อมเวลาปิดรับ';
COMMENT ON TABLE users IS 'ผู้ใช้ระบบ (Admin/Member)';

NOTIFY pgrst, 'reload config';
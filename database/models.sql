-- database/models.sql

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    age INTEGER,
    phone_number VARCHAR(20),
    group_id INTEGER,
    status VARCHAR(20) DEFAULT 'pending',
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS group_id INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deletion_code VARCHAR(10);
ALTER TABLE users ADD COLUMN IF NOT EXISTS level VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS days VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS student_level VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS teacher_bio VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS activity_score INTEGER DEFAULT 0;

-- Groups Table
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    teacher_id BIGINT REFERENCES users(telegram_id) ON DELETE SET NULL,
    group_level VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE groups ADD COLUMN IF NOT EXISTS days VARCHAR(100);
ALTER TABLE groups ADD COLUMN IF NOT EXISTS time VARCHAR(50);
ALTER TABLE groups ADD COLUMN IF NOT EXISTS group_level VARCHAR(50);
ALTER TABLE groups ALTER COLUMN level DROP NOT NULL;

-- Foreign Key from Users to Groups
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_group') THEN
        ALTER TABLE users ADD CONSTRAINT fk_user_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Attendance Table
CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    is_present BOOLEAN NOT NULL DEFAULT TRUE,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, date)
);

ALTER TABLE attendance ADD COLUMN IF NOT EXISTS is_present BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS reason TEXT;

DO $$
BEGIN
  IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='attendance' AND column_name='student_id') THEN
    ALTER TABLE attendance RENAME COLUMN student_id TO user_id;
  END IF;
END $$;


-- Scores Table
CREATE TABLE IF NOT EXISTS scores (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    lesson_number INTEGER NOT NULL,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 25),
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Cycles Table
CREATE TABLE IF NOT EXISTS cycles (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    cycle_number INTEGER NOT NULL,
    total_score INTEGER NOT NULL,
    percentage DECIMAL(5,2) NOT NULL,
    level VARCHAR(50) NOT NULL,
    completed_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE cycles ADD COLUMN IF NOT EXISTS attendance_count INTEGER DEFAULT 0;

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
CREATE INDEX IF NOT EXISTS idx_scores_user ON scores(user_id);
CREATE INDEX IF NOT EXISTS idx_cycles_user ON cycles(user_id);

ALTER TABLE users ADD COLUMN IF NOT EXISTS student_level_updated_at TIMESTAMP WITH TIME ZONE;

CREATE TABLE IF NOT EXISTS level_status (
    level_name VARCHAR(50) PRIMARY KEY,
    status VARCHAR(50),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE level_status ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS teacher_message_logs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    date DATE NOT NULL DEFAULT CURRENT_DATE
);
ALTER TABLE users ADD COLUMN IF NOT EXISTS performance_grade VARCHAR(50);

-- ============================================================
-- PREMIUM TIZIMI UCHUN YANGI USTUNLAR VA JADVALLAR
-- ============================================================

-- Users jadvaliga blok va referral ustunlar
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked_until TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS block_reason TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(30);

-- Groups jadvaliga oylik to'lov ustunlar
ALTER TABLE groups ADD COLUMN IF NOT EXISTS monthly_fee TEXT;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS fee_deadline VARCHAR(100);
ALTER TABLE groups ADD COLUMN IF NOT EXISTS fee_comment TEXT;

-- Premium so'rovlar jadvali (foydalanuvchi to'lov yuboradi)
CREATE TABLE IF NOT EXISTS premium_requests (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    amount TEXT,
    comment TEXT,
    photo_file_id TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    attempt_count INT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_premium_requests_user ON premium_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_premium_requests_status ON premium_requests(status);

-- Faol premium foydalanuvchilar
CREATE TABLE IF NOT EXISTS premium_users (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE UNIQUE,
    activated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    activated_by BIGINT
);
CREATE INDEX IF NOT EXISTS idx_premium_users_expires ON premium_users(expires_at);
CREATE INDEX IF NOT EXISTS idx_premium_users_uid ON premium_users(user_id);

-- Referral tizimi
CREATE TABLE IF NOT EXISTS referral_uses (
    id SERIAL PRIMARY KEY,
    referral_code VARCHAR(30) NOT NULL,
    used_by BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE UNIQUE,
    owner_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    is_staying BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_referral_code ON referral_uses(referral_code);
CREATE INDEX IF NOT EXISTS idx_referral_owner ON referral_uses(owner_id);

-- AI suhbat tarixi (so'nggi 10 ta xabar saqlanadi)
CREATE TABLE IF NOT EXISTS ai_chat_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ai_chat_user ON ai_chat_history(user_id, created_at);

-- Message logs (ustozga xabar chegarasi)
CREATE TABLE IF NOT EXISTS message_logs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_message_logs_user ON message_logs(user_id, sent_at);

-- Referrals
CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    owner_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    referred_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE UNIQUE,
    is_staying BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_referrals_owner ON referrals(owner_id);

-- Premium requests: add photo_id column if missing
ALTER TABLE premium_requests ADD COLUMN IF NOT EXISTS photo_id TEXT;

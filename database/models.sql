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

-- Groups Table
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    teacher_id BIGINT REFERENCES users(telegram_id) ON DELETE SET NULL,
    group_level VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

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

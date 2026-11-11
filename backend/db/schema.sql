-- Enable UUID generator
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Custom Domain Types
DO $$ BEGIN
    CREATE TYPE difficulty_level AS ENUM ('Easy', 'Medium', 'Hard');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE interview_status AS ENUM ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'ABANDONED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE hint_level AS ENUM ('CLARIFICATION', 'SMALL_NUDGE', 'APPROACH_OUTLINE', 'FULL_SOLUTION');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 1. Production Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_email_verified BOOLEAN DEFAULT FALSE,
    leetcode_handle VARCHAR(100) UNIQUE,
    preferred_language VARCHAR(20) DEFAULT 'Java',
    contest_rating INT DEFAULT 1500,
    global_ranking INT,
    user_avatar TEXT,
    easy_solved INT DEFAULT 0,
    medium_solved INT DEFAULT 0,
    hard_solved INT DEFAULT 0,
    total_solved INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Email Verifications / OTP Codes Table
CREATE TABLE IF NOT EXISTS email_verifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    otp_code VARCHAR(6) NOT NULL,
    verification_token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. Password Resets Table
CREATE TABLE IF NOT EXISTS password_resets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    reset_token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 4. Refresh Tokens Table
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 5. Problems Catalog Table
CREATE TABLE IF NOT EXISTS problems (
    frontend_question_id INT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    title_slug VARCHAR(255) NOT NULL,
    difficulty difficulty_level NOT NULL,
    expected_time_minutes INT DEFAULT 30,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 6. Topics Taxonomy
CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- 7. Problem Topics Junction
CREATE TABLE IF NOT EXISTS problem_topics (
    frontend_question_id INT REFERENCES problems(frontend_question_id) ON DELETE CASCADE,
    topic_id INT REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (frontend_question_id, topic_id)
);

-- 8. User Skill Matrix State
CREATE TABLE IF NOT EXISTS user_skills (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    topic_id INT REFERENCES topics(id) ON DELETE CASCADE,
    skill_score DOUBLE PRECISION DEFAULT 0.5,
    last_practiced_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, topic_id)
);

-- 9. Problem Attempt Logs
CREATE TABLE IF NOT EXISTS attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    frontend_question_id INT NOT NULL REFERENCES problems(frontend_question_id) ON DELETE CASCADE,
    time_spent_seconds INT NOT NULL,
    success BOOLEAN NOT NULL,
    submission_count INT DEFAULT 1,
    hints_used INT DEFAULT 0,
    computed_reward DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 10. LinUCB Bandit Model State Matrices
CREATE TABLE IF NOT EXISTS bandit_params (
    arm_id INT PRIMARY KEY REFERENCES problems(frontend_question_id) ON DELETE CASCADE,
    matrix_a JSONB NOT NULL,
    vector_b JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 11. Mock Interview Sessions
CREATE TABLE IF NOT EXISTS mock_interviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interview_type VARCHAR(50) DEFAULT 'DSA',
    difficulty difficulty_level DEFAULT 'Medium',
    target_topics JSONB NOT NULL,
    status interview_status DEFAULT 'IN_PROGRESS',
    time_limit_minutes INT DEFAULT 45,
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    communication_score DOUBLE PRECISION,
    code_quality_score DOUBLE PRECISION,
    time_management_score DOUBLE PRECISION,
    overall_performance_index DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 12. Mock Interview Transcripts
CREATE TABLE IF NOT EXISTS mock_interview_transcripts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    interview_id UUID NOT NULL REFERENCES mock_interviews(id) ON DELETE CASCADE,
    speaker VARCHAR(20) NOT NULL,
    message_text TEXT NOT NULL,
    hint_given hint_level DEFAULT NULL,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_leetcode ON users(leetcode_handle);
CREATE INDEX IF NOT EXISTS idx_attempts_user_date ON attempts(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transcripts_interview ON mock_interview_transcripts(interview_id);
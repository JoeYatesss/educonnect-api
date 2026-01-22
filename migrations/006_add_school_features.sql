-- Migration: Add School Features
-- Description: Creates tables for school accounts, jobs, matches, and interview selections

-- ============================================================================
-- SCHOOL ACCOUNTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS school_accounts (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    school_id INT REFERENCES schools(id) ON DELETE SET NULL,
    school_name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    contact_name VARCHAR(255),
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(50),
    wechat_id VARCHAR(100),
    annual_recruitment_volume VARCHAR(50),
    has_paid BOOLEAN DEFAULT FALSE,
    payment_id VARCHAR(255),
    payment_date TIMESTAMPTZ,
    stripe_customer_id VARCHAR(255),
    detected_country VARCHAR(10),
    detected_currency VARCHAR(10),
    preferred_currency VARCHAR(10),
    max_active_jobs INT DEFAULT 5,
    status VARCHAR(50) DEFAULT 'pending',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_school_accounts_user_id ON school_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_school_accounts_email ON school_accounts(contact_email);

-- ============================================================================
-- SCHOOL JOBS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS school_jobs (
    id SERIAL PRIMARY KEY,
    school_account_id INT NOT NULL REFERENCES school_accounts(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    role_type VARCHAR(100),
    location VARCHAR(255),
    city VARCHAR(100),
    province VARCHAR(100),
    school_info TEXT,
    subjects TEXT[],
    age_groups TEXT[],
    experience_required VARCHAR(100),
    chinese_required BOOLEAN DEFAULT FALSE,
    qualification VARCHAR(255),
    salary_min INT,
    salary_max INT,
    salary_display VARCHAR(100),
    description TEXT,
    key_responsibilities TEXT,
    requirements TEXT,
    benefits TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_school_jobs_school_account ON school_jobs(school_account_id);
CREATE INDEX IF NOT EXISTS idx_school_jobs_active ON school_jobs(is_active);

-- ============================================================================
-- SCHOOL JOB MATCHES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS school_job_matches (
    id SERIAL PRIMARY KEY,
    school_job_id INT NOT NULL REFERENCES school_jobs(id) ON DELETE CASCADE,
    teacher_id INT NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
    school_account_id INT NOT NULL REFERENCES school_accounts(id) ON DELETE CASCADE,
    match_score DECIMAL(5,2) NOT NULL,
    match_reasons TEXT[],
    matched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(school_job_id, teacher_id)
);

CREATE INDEX IF NOT EXISTS idx_school_job_matches_job ON school_job_matches(school_job_id);
CREATE INDEX IF NOT EXISTS idx_school_job_matches_teacher ON school_job_matches(teacher_id);
CREATE INDEX IF NOT EXISTS idx_school_job_matches_school ON school_job_matches(school_account_id);

-- ============================================================================
-- SCHOOL INTERVIEW SELECTIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS school_interview_selections (
    id SERIAL PRIMARY KEY,
    school_account_id INT NOT NULL REFERENCES school_accounts(id) ON DELETE CASCADE,
    teacher_id INT NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
    school_job_id INT REFERENCES school_jobs(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'selected_for_interview',
    notes TEXT,
    selected_at TIMESTAMPTZ DEFAULT NOW(),
    status_updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(school_account_id, teacher_id, school_job_id)
);

CREATE INDEX IF NOT EXISTS idx_school_interview_selections_school ON school_interview_selections(school_account_id);
CREATE INDEX IF NOT EXISTS idx_school_interview_selections_teacher ON school_interview_selections(teacher_id);
CREATE INDEX IF NOT EXISTS idx_school_interview_selections_job ON school_interview_selections(school_job_id);
CREATE INDEX IF NOT EXISTS idx_school_interview_selections_status ON school_interview_selections(status);

-- ============================================================================
-- SCHOOL SAVED TEACHERS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS school_saved_teachers (
    id SERIAL PRIMARY KEY,
    school_account_id INT NOT NULL REFERENCES school_accounts(id) ON DELETE CASCADE,
    teacher_id INT NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(school_account_id, teacher_id)
);

CREATE INDEX IF NOT EXISTS idx_school_saved_teachers_school ON school_saved_teachers(school_account_id);
CREATE INDEX IF NOT EXISTS idx_school_saved_teachers_teacher ON school_saved_teachers(teacher_id);

-- ============================================================================
-- TRIGGERS FOR updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_school_accounts_updated_at ON school_accounts;
CREATE TRIGGER update_school_accounts_updated_at
    BEFORE UPDATE ON school_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_school_jobs_updated_at ON school_jobs;
CREATE TRIGGER update_school_jobs_updated_at
    BEFORE UPDATE ON school_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- TRIGGER FOR status_updated_at ON INTERVIEW SELECTIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_selection_status_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        NEW.status_updated_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_selection_status_updated_at ON school_interview_selections;
CREATE TRIGGER update_selection_status_updated_at
    BEFORE UPDATE ON school_interview_selections
    FOR EACH ROW
    EXECUTE FUNCTION update_selection_status_timestamp();

-- ============================================================================
-- RLS POLICIES
-- ============================================================================

ALTER TABLE school_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_job_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_interview_selections ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_saved_teachers ENABLE ROW LEVEL SECURITY;

-- School accounts: users can only see their own account
CREATE POLICY "Users can view own school account"
    ON school_accounts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update own school account"
    ON school_accounts FOR UPDATE
    USING (auth.uid() = user_id);

-- School jobs: school owners can manage their jobs
CREATE POLICY "School owners can manage their jobs"
    ON school_jobs FOR ALL
    USING (school_account_id IN (
        SELECT id FROM school_accounts WHERE user_id = auth.uid()
    ));

-- Teachers can view active jobs
CREATE POLICY "Teachers can view active jobs"
    ON school_jobs FOR SELECT
    USING (is_active = TRUE);

-- School job matches: school owners can view their matches
CREATE POLICY "School owners can view their matches"
    ON school_job_matches FOR SELECT
    USING (school_account_id IN (
        SELECT id FROM school_accounts WHERE user_id = auth.uid()
    ));

-- Interview selections: school owners can manage their selections
CREATE POLICY "School owners can manage their selections"
    ON school_interview_selections FOR ALL
    USING (school_account_id IN (
        SELECT id FROM school_accounts WHERE user_id = auth.uid()
    ));

-- Saved teachers: school owners can manage their saved teachers
CREATE POLICY "School owners can manage their saved teachers"
    ON school_saved_teachers FOR ALL
    USING (school_account_id IN (
        SELECT id FROM school_accounts WHERE user_id = auth.uid()
    ));

-- Service role bypass for all tables (for API operations)
CREATE POLICY "Service role has full access to school_accounts"
    ON school_accounts FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to school_jobs"
    ON school_jobs FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to school_job_matches"
    ON school_job_matches FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to school_interview_selections"
    ON school_interview_selections FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to school_saved_teachers"
    ON school_saved_teachers FOR ALL
    USING (auth.role() = 'service_role');

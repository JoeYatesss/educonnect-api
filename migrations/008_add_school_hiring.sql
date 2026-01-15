-- EduConnect Database Schema
-- Migration: 008_add_school_hiring
-- Description: Add school hiring features (job posting, matching, interview selection)

-- ============================================================================
-- CUSTOM TYPES (ENUMS)
-- ============================================================================

-- Interview selection status enum
CREATE TYPE interview_selection_status AS ENUM (
  'selected_for_interview',
  'interview_scheduled',
  'interview_completed',
  'offer_extended',
  'offer_accepted',
  'offer_declined',
  'withdrawn'
);

-- ============================================================================
-- ALTER EXISTING TABLES
-- ============================================================================

-- Add max_active_jobs column to school_accounts
ALTER TABLE school_accounts ADD COLUMN max_active_jobs INTEGER DEFAULT 5;

-- ============================================================================
-- TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- School Jobs Table
-- Job postings created by schools
-- ----------------------------------------------------------------------------
CREATE TABLE school_jobs (
  id BIGSERIAL PRIMARY KEY,
  school_account_id BIGINT NOT NULL REFERENCES school_accounts(id) ON DELETE CASCADE,

  -- Job Information
  title VARCHAR(255) NOT NULL,
  role_type VARCHAR(100), -- 'teacher', 'administrator', 'counselor', etc.

  -- Location & School Info
  location VARCHAR(500),
  city VARCHAR(100),
  province VARCHAR(100),
  school_info TEXT, -- Additional school context for the job

  -- Job Requirements
  subjects TEXT[], -- Array of subjects needed
  age_groups TEXT[], -- Array: ['kindergarten', 'primary', 'middle_school', 'high_school']
  experience_required VARCHAR(100), -- '0-2 years', '3-5 years', '5+ years'
  chinese_required BOOLEAN DEFAULT FALSE,
  qualification TEXT,

  -- Compensation
  salary_min INTEGER, -- In RMB/month
  salary_max INTEGER,
  salary_display VARCHAR(100), -- For display: '25,000 - 35,000 RMB/month'

  -- Description
  description TEXT,
  key_responsibilities TEXT,
  requirements TEXT,
  benefits TEXT,

  -- Status
  is_active BOOLEAN DEFAULT TRUE,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- School Job Matches Table
-- Tracks matches between school jobs and teachers
-- ----------------------------------------------------------------------------
CREATE TABLE school_job_matches (
  id BIGSERIAL PRIMARY KEY,
  school_job_id BIGINT NOT NULL REFERENCES school_jobs(id) ON DELETE CASCADE,
  teacher_id BIGINT NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  school_account_id BIGINT NOT NULL REFERENCES school_accounts(id) ON DELETE CASCADE,

  -- Match Information
  match_score NUMERIC(5,2) CHECK (match_score >= 0 AND match_score <= 100),
  match_reasons TEXT[],

  -- Timestamps
  matched_at TIMESTAMPTZ DEFAULT NOW(),

  -- Unique constraint: one match per job-teacher pair
  UNIQUE(school_job_id, teacher_id)
);

-- ----------------------------------------------------------------------------
-- School Interview Selections Table
-- Tracks teachers selected for interview by schools
-- ----------------------------------------------------------------------------
CREATE TABLE school_interview_selections (
  id BIGSERIAL PRIMARY KEY,
  school_account_id BIGINT NOT NULL REFERENCES school_accounts(id) ON DELETE CASCADE,
  teacher_id BIGINT NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  school_job_id BIGINT REFERENCES school_jobs(id) ON DELETE SET NULL,

  -- Selection Information
  status interview_selection_status DEFAULT 'selected_for_interview',
  notes TEXT, -- School's internal notes

  -- Timestamps
  selected_at TIMESTAMPTZ DEFAULT NOW(),
  status_updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Unique constraint: one selection per school-teacher-job combination
  UNIQUE(school_account_id, teacher_id, school_job_id)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- School jobs indexes
CREATE INDEX idx_school_jobs_school_account_id ON school_jobs(school_account_id);
CREATE INDEX idx_school_jobs_is_active ON school_jobs(is_active);
CREATE INDEX idx_school_jobs_city ON school_jobs(city);
CREATE INDEX idx_school_jobs_created_at ON school_jobs(created_at DESC);

-- School job matches indexes
CREATE INDEX idx_school_job_matches_school_job_id ON school_job_matches(school_job_id);
CREATE INDEX idx_school_job_matches_teacher_id ON school_job_matches(teacher_id);
CREATE INDEX idx_school_job_matches_school_account_id ON school_job_matches(school_account_id);
CREATE INDEX idx_school_job_matches_score ON school_job_matches(match_score DESC);

-- School interview selections indexes
CREATE INDEX idx_interview_selections_school_account_id ON school_interview_selections(school_account_id);
CREATE INDEX idx_interview_selections_teacher_id ON school_interview_selections(teacher_id);
CREATE INDEX idx_interview_selections_school_job_id ON school_interview_selections(school_job_id);
CREATE INDEX idx_interview_selections_status ON school_interview_selections(status);
CREATE INDEX idx_interview_selections_selected_at ON school_interview_selections(selected_at DESC);

-- ============================================================================
-- TRIGGERS FOR updated_at
-- ============================================================================

-- Apply trigger to school_jobs
CREATE TRIGGER update_school_jobs_updated_at BEFORE UPDATE ON school_jobs
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to school_interview_selections (for status_updated_at)
CREATE OR REPLACE FUNCTION update_interview_selection_status_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.status IS DISTINCT FROM OLD.status THEN
    NEW.status_updated_at = NOW();
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_interview_selection_status BEFORE UPDATE ON school_interview_selections
  FOR EACH ROW EXECUTE FUNCTION update_interview_selection_status_timestamp();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all new tables
ALTER TABLE school_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_job_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_interview_selections ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- School Jobs Table RLS Policies
-- ----------------------------------------------------------------------------

-- Schools can view their own jobs
CREATE POLICY "Schools can view own jobs"
  ON school_jobs FOR SELECT
  USING (
    school_account_id IN (
      SELECT id FROM school_accounts WHERE user_id = auth.uid()
    )
  );

-- Schools can manage their own jobs
CREATE POLICY "Schools can manage own jobs"
  ON school_jobs FOR ALL
  USING (
    school_account_id IN (
      SELECT id FROM school_accounts WHERE user_id = auth.uid()
    )
  );

-- Admins can view all school jobs
CREATE POLICY "Admins can view all school jobs"
  ON school_jobs FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- Admins can manage all school jobs
CREATE POLICY "Admins can manage all school jobs"
  ON school_jobs FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- School Job Matches Table RLS Policies
-- ----------------------------------------------------------------------------

-- Schools can view their own job matches
CREATE POLICY "Schools can view own job matches"
  ON school_job_matches FOR SELECT
  USING (
    school_account_id IN (
      SELECT id FROM school_accounts WHERE user_id = auth.uid()
    )
  );

-- Admins can view all job matches
CREATE POLICY "Admins can view all job matches"
  ON school_job_matches FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- Admins can manage all job matches
CREATE POLICY "Admins can manage all job matches"
  ON school_job_matches FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- School Interview Selections Table RLS Policies
-- ----------------------------------------------------------------------------

-- Schools can view their own selections
CREATE POLICY "Schools can view own selections"
  ON school_interview_selections FOR SELECT
  USING (
    school_account_id IN (
      SELECT id FROM school_accounts WHERE user_id = auth.uid()
    )
  );

-- Schools can manage their own selections
CREATE POLICY "Schools can manage own selections"
  ON school_interview_selections FOR ALL
  USING (
    school_account_id IN (
      SELECT id FROM school_accounts WHERE user_id = auth.uid()
    )
  );

-- Admins can view all selections
CREATE POLICY "Admins can view all selections"
  ON school_interview_selections FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- Admins can manage all selections
CREATE POLICY "Admins can manage all selections"
  ON school_interview_selections FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE school_jobs IS 'Job postings created by schools for hiring teachers';
COMMENT ON TABLE school_job_matches IS 'Matches between school jobs and teachers based on criteria';
COMMENT ON TABLE school_interview_selections IS 'Teachers selected for interview by schools';

COMMENT ON COLUMN school_jobs.school_info IS 'Additional information about the school for this job posting';
COMMENT ON COLUMN school_jobs.subjects IS 'Array of subjects the job requires (e.g., Math, English)';
COMMENT ON COLUMN school_jobs.age_groups IS 'Array of age groups (kindergarten, primary, middle_school, high_school)';
COMMENT ON COLUMN school_jobs.experience_required IS 'Required experience level (0-2 years, 3-5 years, 5+ years)';
COMMENT ON COLUMN school_jobs.salary_min IS 'Minimum monthly salary in RMB';
COMMENT ON COLUMN school_jobs.salary_max IS 'Maximum monthly salary in RMB';
COMMENT ON COLUMN school_jobs.key_responsibilities IS 'Key responsibilities for the role';

COMMENT ON COLUMN school_job_matches.match_score IS 'Match score 0-100 based on criteria matching';
COMMENT ON COLUMN school_job_matches.match_reasons IS 'Array of reasons explaining the match score';

COMMENT ON COLUMN school_interview_selections.status IS 'Current status in the interview process';
COMMENT ON COLUMN school_interview_selections.notes IS 'School internal notes about the selection';

COMMENT ON COLUMN school_accounts.max_active_jobs IS 'Maximum number of active job postings allowed (default 5)';

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================

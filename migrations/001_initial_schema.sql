-- EduConnect Database Schema v2
-- Migration: 001_initial_schema
-- Description: Complete database setup for EduConnect platform v2

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

-- Enable UUID extension for generating unique identifiers
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- CUSTOM TYPES (ENUMS)
-- ============================================================================

-- Teacher/Application status enum (7-stage workflow)
CREATE TYPE application_status AS ENUM (
  'pending',
  'document_verification',
  'school_matching',
  'interview_scheduled',
  'interview_completed',
  'offer_extended',
  'placed',
  'declined'
);

-- Admin roles
CREATE TYPE admin_role AS ENUM ('admin', 'master_admin');

-- School types
CREATE TYPE school_type AS ENUM (
  'international',
  'bilingual',
  'public',
  'private'
);

-- ============================================================================
-- TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Teachers Table
-- ----------------------------------------------------------------------------
CREATE TABLE teachers (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Personal Information
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  phone VARCHAR(20),
  nationality VARCHAR(100),

  -- Professional Information
  years_experience VARCHAR(20),
  education TEXT,
  teaching_experience TEXT,
  subject_specialty VARCHAR(100),
  preferred_location VARCHAR(255),
  preferred_age_group VARCHAR(100),

  -- Files
  intro_video_path TEXT,
  headshot_photo_path TEXT,
  cv_path TEXT,

  -- Social Media
  linkedin VARCHAR(255),
  instagram VARCHAR(255),
  wechat_id VARCHAR(100),

  -- Additional
  professional_experience TEXT,
  additional_info TEXT,

  -- Status & Payment
  status application_status DEFAULT 'pending',
  has_paid BOOLEAN DEFAULT false,
  payment_id VARCHAR(255),
  payment_date TIMESTAMPTZ,
  stripe_customer_id VARCHAR(255),

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Admin Users Table
-- ----------------------------------------------------------------------------
CREATE TABLE admin_users (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name VARCHAR(255),
  role admin_role DEFAULT 'admin',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Schools Table
-- ----------------------------------------------------------------------------
CREATE TABLE schools (
  id BIGSERIAL PRIMARY KEY,

  -- Basic Information (Bilingual)
  name VARCHAR(255) NOT NULL,
  name_chinese VARCHAR(255),
  location VARCHAR(500),
  location_chinese VARCHAR(500),
  city VARCHAR(100),
  province VARCHAR(100),

  -- School Details
  school_type school_type,
  age_groups TEXT[], -- Array: ['primary', 'middle_school', 'high_school']
  subjects_needed TEXT[], -- Array: ['english', 'math', 'science']

  -- Requirements
  experience_required VARCHAR(100),
  chinese_required BOOLEAN DEFAULT false,

  -- Compensation
  salary_range VARCHAR(100),
  contract_type VARCHAR(100),
  benefits TEXT,

  -- Description
  description TEXT,

  -- Contact Information
  contact_name VARCHAR(255),
  contact_email VARCHAR(255),
  contact_phone VARCHAR(50),

  -- Status
  is_active BOOLEAN DEFAULT true,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Jobs Table
-- ----------------------------------------------------------------------------
CREATE TABLE jobs (
  id BIGSERIAL PRIMARY KEY,
  school_id BIGINT REFERENCES schools(id) ON DELETE SET NULL,

  -- Job Information
  title VARCHAR(255) NOT NULL,
  company VARCHAR(255),
  location VARCHAR(500),
  location_chinese VARCHAR(500),
  city VARCHAR(100),
  province VARCHAR(100),

  -- Job Details
  salary VARCHAR(100),
  experience VARCHAR(100),
  chinese_required BOOLEAN DEFAULT false,
  qualification TEXT,
  contract_type VARCHAR(100),
  job_functions TEXT,

  -- Description
  description TEXT,
  requirements TEXT,
  benefits TEXT,

  -- Arrays
  age_groups TEXT[],
  subjects TEXT[],

  -- Status
  is_active BOOLEAN DEFAULT true,
  is_new BOOLEAN DEFAULT true,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Teacher School Matches Table (Potential Matches)
-- ----------------------------------------------------------------------------
CREATE TABLE teacher_school_matches (
  id BIGSERIAL PRIMARY KEY,
  teacher_id BIGINT REFERENCES teachers(id) ON DELETE CASCADE,
  school_id BIGINT REFERENCES schools(id) ON DELETE CASCADE,

  -- Match Information
  match_score NUMERIC(5,2) CHECK (match_score >= 0 AND match_score <= 100),
  match_reasons TEXT[], -- Array of reasons for the match

  -- Submission Status
  is_submitted BOOLEAN DEFAULT false,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Unique constraint: one match per teacher-school pair
  UNIQUE(teacher_id, school_id)
);

-- ----------------------------------------------------------------------------
-- Teacher School Applications Table (Actual Submissions)
-- ----------------------------------------------------------------------------
CREATE TABLE teacher_school_applications (
  id BIGSERIAL PRIMARY KEY,
  teacher_id BIGINT REFERENCES teachers(id) ON DELETE CASCADE,
  school_id BIGINT REFERENCES schools(id) ON DELETE CASCADE,
  match_id BIGINT REFERENCES teacher_school_matches(id) ON DELETE SET NULL,

  -- Application Status
  status application_status DEFAULT 'pending',

  -- Admin Information
  submitted_by UUID REFERENCES admin_users(id),
  notes TEXT,

  -- Timestamps
  submitted_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Application Status History Table
-- ----------------------------------------------------------------------------
CREATE TABLE application_status_history (
  id BIGSERIAL PRIMARY KEY,
  application_id BIGINT REFERENCES teacher_school_applications(id) ON DELETE CASCADE,

  -- Status Change
  from_status application_status,
  to_status application_status NOT NULL,

  -- Admin Information
  changed_by UUID REFERENCES admin_users(id),
  notes TEXT,

  -- Timestamp
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Teacher Status History Table
-- ----------------------------------------------------------------------------
CREATE TABLE teacher_status_history (
  id BIGSERIAL PRIMARY KEY,
  teacher_id BIGINT REFERENCES teachers(id) ON DELETE CASCADE,

  -- Status Change
  from_status application_status,
  to_status application_status NOT NULL,

  -- Admin Information
  changed_by UUID REFERENCES admin_users(id),
  notes TEXT,

  -- Timestamp
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Payments Table
-- ----------------------------------------------------------------------------
CREATE TABLE payments (
  id BIGSERIAL PRIMARY KEY,
  teacher_id BIGINT REFERENCES teachers(id) ON DELETE CASCADE,

  -- Stripe Information
  stripe_payment_intent_id VARCHAR(255) UNIQUE NOT NULL,
  stripe_customer_id VARCHAR(255),

  -- Payment Details
  amount INTEGER NOT NULL, -- Amount in cents
  currency VARCHAR(3) DEFAULT 'USD',
  status VARCHAR(50), -- 'pending', 'succeeded', 'failed', 'refunded'
  payment_method VARCHAR(50),
  receipt_url TEXT,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Job Interests Table (for public job interest submissions)
-- ----------------------------------------------------------------------------
CREATE TABLE job_interests (
  id BIGSERIAL PRIMARY KEY,
  job_id BIGINT REFERENCES jobs(id) ON DELETE CASCADE,

  -- Contact Information
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  email VARCHAR(255),
  phone VARCHAR(50),

  -- Preferences
  preferred_location VARCHAR(255),
  teaching_subject VARCHAR(100),
  experience VARCHAR(100),
  message TEXT,

  -- Status
  status VARCHAR(50) DEFAULT 'new',

  -- Timestamp
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Teachers table indexes
CREATE INDEX idx_teachers_user_id ON teachers(user_id);
CREATE INDEX idx_teachers_email ON teachers(email);
CREATE INDEX idx_teachers_status ON teachers(status);
CREATE INDEX idx_teachers_has_paid ON teachers(has_paid);
CREATE INDEX idx_teachers_created_at ON teachers(created_at DESC);

-- Admin users indexes
CREATE INDEX idx_admin_users_is_active ON admin_users(is_active);

-- Schools table indexes
CREATE INDEX idx_schools_city ON schools(city);
CREATE INDEX idx_schools_province ON schools(province);
CREATE INDEX idx_schools_is_active ON schools(is_active);
CREATE INDEX idx_schools_school_type ON schools(school_type);

-- Jobs table indexes
CREATE INDEX idx_jobs_school_id ON jobs(school_id);
CREATE INDEX idx_jobs_city ON jobs(city);
CREATE INDEX idx_jobs_is_active ON jobs(is_active);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);

-- Matches table indexes
CREATE INDEX idx_matches_teacher_id ON teacher_school_matches(teacher_id);
CREATE INDEX idx_matches_school_id ON teacher_school_matches(school_id);
CREATE INDEX idx_matches_is_submitted ON teacher_school_matches(is_submitted);
CREATE INDEX idx_matches_score ON teacher_school_matches(match_score DESC);

-- Applications table indexes
CREATE INDEX idx_applications_teacher_id ON teacher_school_applications(teacher_id);
CREATE INDEX idx_applications_school_id ON teacher_school_applications(school_id);
CREATE INDEX idx_applications_status ON teacher_school_applications(status);
CREATE INDEX idx_applications_submitted_at ON teacher_school_applications(submitted_at DESC);

-- Application history indexes
CREATE INDEX idx_app_history_application_id ON application_status_history(application_id);
CREATE INDEX idx_app_history_created_at ON application_status_history(created_at DESC);

-- Teacher history indexes
CREATE INDEX idx_teacher_history_teacher_id ON teacher_status_history(teacher_id);
CREATE INDEX idx_teacher_history_created_at ON teacher_status_history(created_at DESC);

-- Payments table indexes
CREATE INDEX idx_payments_teacher_id ON payments(teacher_id);
CREATE INDEX idx_payments_stripe_payment_intent_id ON payments(stripe_payment_intent_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_created_at ON payments(created_at DESC);

-- Job interests indexes
CREATE INDEX idx_job_interests_job_id ON job_interests(job_id);
CREATE INDEX idx_job_interests_email ON job_interests(email);
CREATE INDEX idx_job_interests_created_at ON job_interests(created_at DESC);

-- ============================================================================
-- TRIGGERS FOR updated_at
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_teachers_updated_at BEFORE UPDATE ON teachers
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admin_users_updated_at BEFORE UPDATE ON admin_users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_schools_updated_at BEFORE UPDATE ON schools
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_matches_updated_at BEFORE UPDATE ON teacher_school_matches
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_applications_updated_at BEFORE UPDATE ON teacher_school_applications
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payments_updated_at BEFORE UPDATE ON payments
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE teachers ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE schools ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_school_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_school_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_interests ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- Teachers Table RLS Policies
-- ----------------------------------------------------------------------------

-- Teachers can view their own profile
CREATE POLICY "Teachers can view own profile"
  ON teachers FOR SELECT
  USING (auth.uid() = user_id);

-- Teachers can update their own profile
CREATE POLICY "Teachers can update own profile"
  ON teachers FOR UPDATE
  USING (auth.uid() = user_id);

-- Teachers can insert their own profile (during signup)
CREATE POLICY "Teachers can insert own profile"
  ON teachers FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Admins can view all teachers
CREATE POLICY "Admins can view all teachers"
  ON teachers FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- Admins can update any teacher
CREATE POLICY "Admins can update teachers"
  ON teachers FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- Admin Users Table RLS Policies
-- ----------------------------------------------------------------------------

-- Only active admins can view admin users
CREATE POLICY "Admins can view admin users"
  ON admin_users FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM admin_users AS a
      WHERE a.id = auth.uid()
      AND a.is_active = true
    )
  );

-- Only master admins can modify admin users
CREATE POLICY "Master admins can manage admins"
  ON admin_users FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users AS a
      WHERE a.id = auth.uid()
      AND a.role = 'master_admin'
      AND a.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- Schools Table RLS Policies
-- ----------------------------------------------------------------------------

-- Teachers CANNOT view schools (business requirement)
-- Only admins can view schools
CREATE POLICY "Only admins can view schools"
  ON schools FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- Only admins can modify schools
CREATE POLICY "Admins can manage schools"
  ON schools FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- Jobs Table RLS Policies
-- ----------------------------------------------------------------------------

-- Public can view active jobs (no auth required)
CREATE POLICY "Public can view active jobs"
  ON jobs FOR SELECT
  USING (is_active = true);

-- Admins can manage all jobs
CREATE POLICY "Admins can manage jobs"
  ON jobs FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- Teacher School Matches RLS Policies
-- ----------------------------------------------------------------------------

-- Teachers can view their own matches (ANONYMIZED via backend)
CREATE POLICY "Teachers can view own matches"
  ON teacher_school_matches FOR SELECT
  USING (
    teacher_id IN (
      SELECT id FROM teachers WHERE user_id = auth.uid()
    )
  );

-- Admins can view all matches
CREATE POLICY "Admins can view all matches"
  ON teacher_school_matches FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- Admins can manage matches
CREATE POLICY "Admins can manage matches"
  ON teacher_school_matches FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- Teacher School Applications RLS Policies
-- ----------------------------------------------------------------------------

-- Teachers can view their own applications (ANONYMIZED via backend)
CREATE POLICY "Teachers can view own applications"
  ON teacher_school_applications FOR SELECT
  USING (
    teacher_id IN (
      SELECT id FROM teachers WHERE user_id = auth.uid()
    )
  );

-- Admins can view all applications
CREATE POLICY "Admins can view all applications"
  ON teacher_school_applications FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- Admins can manage applications
CREATE POLICY "Admins can manage applications"
  ON teacher_school_applications FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- Application Status History RLS Policies
-- ----------------------------------------------------------------------------

-- Admins can view all application history
CREATE POLICY "Admins can view application history"
  ON application_status_history FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- Teacher Status History RLS Policies
-- ----------------------------------------------------------------------------

-- Teachers can view their own status history
CREATE POLICY "Teachers can view own status history"
  ON teacher_status_history FOR SELECT
  USING (
    teacher_id IN (
      SELECT id FROM teachers WHERE user_id = auth.uid()
    )
  );

-- Admins can view all teacher status history
CREATE POLICY "Admins can view all teacher history"
  ON teacher_status_history FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- Payments Table RLS Policies
-- ----------------------------------------------------------------------------

-- Teachers can view their own payments
CREATE POLICY "Teachers can view own payments"
  ON payments FOR SELECT
  USING (
    teacher_id IN (
      SELECT id FROM teachers WHERE user_id = auth.uid()
    )
  );

-- Admins can view all payments
CREATE POLICY "Admins can view all payments"
  ON payments FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- Job Interests RLS Policies
-- ----------------------------------------------------------------------------

-- Public can insert job interests
CREATE POLICY "Public can submit job interests"
  ON job_interests FOR INSERT
  WITH CHECK (true);

-- Admins can view all job interests
CREATE POLICY "Admins can view job interests"
  ON job_interests FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ============================================================================
-- STORAGE BUCKETS (for Supabase Storage)
-- ============================================================================

-- Note: These need to be created in Supabase Dashboard or via API
-- Buckets needed:
-- 1. 'cvs' - for CV/resume uploads
-- 2. 'intro-videos' - for teacher intro videos
-- 3. 'headshot-photos' - for teacher headshot photos

-- Storage policies (run these after creating buckets):
--
-- For 'cvs' bucket:
-- - Teachers can upload to their own folder
-- - Admins can read all
--
-- For 'intro-videos' bucket:
-- - Teachers can upload to their own folder
-- - Admins can read all
--
-- For 'headshot-photos' bucket:
-- - Teachers can upload to their own folder
-- - Admins can read all

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE teachers IS 'Teacher profiles and application data';
COMMENT ON TABLE admin_users IS 'Admin users with role-based access';
COMMENT ON TABLE schools IS 'Schools/institutions seeking teachers';
COMMENT ON TABLE jobs IS 'Job postings for teaching positions';
COMMENT ON TABLE teacher_school_matches IS 'Potential matches between teachers and schools';
COMMENT ON TABLE teacher_school_applications IS 'Actual applications submitted by admin on behalf of teachers';
COMMENT ON TABLE application_status_history IS 'History of status changes for applications';
COMMENT ON TABLE teacher_status_history IS 'History of status changes for teachers';
COMMENT ON TABLE payments IS 'Payment records for teacher school access';
COMMENT ON TABLE job_interests IS 'Public job interest submissions';

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================

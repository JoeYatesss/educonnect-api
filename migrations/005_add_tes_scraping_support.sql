-- Migration: Add TES.com job scraping support
-- Date: 2026-01-06
-- Description: Adds fields to support external job scraping from TES.com

-- ============================================
-- 1. ADD SOURCE TRACKING FIELDS TO JOBS TABLE
-- ============================================

-- Source identifier (manual = internal, tes = scraped from TES.com)
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'manual';

-- External job ID for deduplication
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS external_id VARCHAR(255);

-- Link to original posting
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS external_url TEXT;

-- When the job was scraped
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS scraped_at TIMESTAMPTZ;

-- ============================================
-- 2. ADD TES-SPECIFIC FIELDS TO JOBS TABLE
-- ============================================

-- Application closing/expiry date
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS application_deadline TIMESTAMPTZ;

-- Job start date (e.g., "September 2025", "Immediately")
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS start_date VARCHAR(100);

-- Whether visa sponsorship is provided
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS visa_sponsorship BOOLEAN DEFAULT NULL;

-- Accommodation details
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS accommodation_provided VARCHAR(255);

-- School type (international, bilingual, public, private, kindergarten)
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS school_type VARCHAR(50);

-- Contract term (permanent, fixed_term, temporary)
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS contract_term VARCHAR(50);

-- ============================================
-- 3. ADD INDEXES FOR NEW FIELDS
-- ============================================

-- Index for filtering by source
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);

-- Index for filtering by application deadline
CREATE INDEX IF NOT EXISTS idx_jobs_deadline ON jobs(application_deadline);

-- Unique constraint to prevent duplicate external jobs
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_external_source_id
ON jobs(source, external_id)
WHERE external_id IS NOT NULL;

-- Index for school type filtering
CREATE INDEX IF NOT EXISTS idx_jobs_school_type ON jobs(school_type);

-- ============================================
-- 4. MODIFY TEACHER_SCHOOL_MATCHES FOR JOBS
-- ============================================

-- Add job_id to allow matching against jobs (not just schools)
ALTER TABLE teacher_school_matches ADD COLUMN IF NOT EXISTS job_id BIGINT REFERENCES jobs(id) ON DELETE CASCADE;

-- Make school_id nullable (either school_id OR job_id should be set)
ALTER TABLE teacher_school_matches ALTER COLUMN school_id DROP NOT NULL;

-- Add constraint: either school_id or job_id must be set, but not both
ALTER TABLE teacher_school_matches DROP CONSTRAINT IF EXISTS match_school_or_job_check;
ALTER TABLE teacher_school_matches ADD CONSTRAINT match_school_or_job_check
CHECK (
    (school_id IS NOT NULL AND job_id IS NULL) OR
    (school_id IS NULL AND job_id IS NOT NULL)
);

-- Index for job matches
CREATE INDEX IF NOT EXISTS idx_matches_job_id ON teacher_school_matches(job_id);

-- Unique constraint for teacher-job pairs
CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_teacher_job
ON teacher_school_matches(teacher_id, job_id)
WHERE job_id IS NOT NULL;

-- ============================================
-- 5. CREATE SCRAPE RUNS LOGGING TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS scrape_runs (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'running', -- running, completed, failed
    jobs_found INTEGER DEFAULT 0,
    jobs_imported INTEGER DEFAULT 0,
    jobs_updated INTEGER DEFAULT 0,
    jobs_skipped INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSONB, -- Additional info like page count, duration
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for scrape_runs
CREATE INDEX IF NOT EXISTS idx_scrape_runs_source ON scrape_runs(source);
CREATE INDEX IF NOT EXISTS idx_scrape_runs_started ON scrape_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scrape_runs_status ON scrape_runs(status);

-- ============================================
-- 6. RLS POLICIES FOR NEW TABLE
-- ============================================

-- Enable RLS on scrape_runs
ALTER TABLE scrape_runs ENABLE ROW LEVEL SECURITY;

-- Admin-only access to scrape_runs
CREATE POLICY admin_scrape_runs_all ON scrape_runs
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================
-- 7. COMMENTS FOR DOCUMENTATION
-- ============================================

COMMENT ON COLUMN jobs.source IS 'Origin of job posting: manual (internal) or tes (scraped from TES.com)';
COMMENT ON COLUMN jobs.external_id IS 'External job ID from source website for deduplication';
COMMENT ON COLUMN jobs.external_url IS 'URL to original job posting on source website';
COMMENT ON COLUMN jobs.scraped_at IS 'Timestamp when job was scraped from external source';
COMMENT ON COLUMN jobs.application_deadline IS 'Closing date for applications';
COMMENT ON COLUMN jobs.start_date IS 'When the job/position starts';
COMMENT ON COLUMN jobs.visa_sponsorship IS 'Whether the employer sponsors work visas';
COMMENT ON COLUMN jobs.accommodation_provided IS 'Details about housing/accommodation benefits';
COMMENT ON COLUMN jobs.school_type IS 'Type of school: international, bilingual, public, private, kindergarten';
COMMENT ON COLUMN jobs.contract_term IS 'Contract duration type: permanent, fixed_term, temporary';

COMMENT ON COLUMN teacher_school_matches.job_id IS 'Reference to job posting (if matching against external job)';

COMMENT ON TABLE scrape_runs IS 'Audit log of external job scraping operations';

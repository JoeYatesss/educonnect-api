-- EduConnect Database Schema
-- Migration: 006_create_school_accounts
-- Description: Create school accounts system for school login and dashboard

-- ============================================================================
-- CUSTOM TYPES (ENUMS)
-- ============================================================================

-- School account status
CREATE TYPE school_account_status AS ENUM (
  'pending',
  'approved',
  'suspended'
);

-- ============================================================================
-- TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- School Accounts Table
-- Links authenticated users to school profiles
-- ----------------------------------------------------------------------------
CREATE TABLE school_accounts (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  school_id BIGINT REFERENCES schools(id) ON DELETE SET NULL,

  -- Registration Information
  school_name VARCHAR(255) NOT NULL,
  city VARCHAR(100) NOT NULL,
  wechat_id VARCHAR(100),
  annual_recruitment_volume VARCHAR(50), -- '1-5', '6-10', '11-20', '20+'

  -- Contact Information
  contact_name VARCHAR(100),
  contact_email VARCHAR(255) NOT NULL,
  contact_phone VARCHAR(50),

  -- Payment Status
  has_paid BOOLEAN DEFAULT FALSE,
  payment_id VARCHAR(255),
  payment_date TIMESTAMPTZ,
  stripe_customer_id VARCHAR(255),

  -- Currency Detection (like teachers)
  detected_country VARCHAR(10),
  detected_currency VARCHAR(3),
  preferred_currency VARCHAR(3),

  -- Status
  status school_account_status DEFAULT 'pending',
  is_active BOOLEAN DEFAULT TRUE,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- School Saved Teachers Table (Bookmarks)
-- ----------------------------------------------------------------------------
CREATE TABLE school_saved_teachers (
  id BIGSERIAL PRIMARY KEY,
  school_account_id BIGINT NOT NULL REFERENCES school_accounts(id) ON DELETE CASCADE,
  teacher_id BIGINT NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),

  -- Unique constraint: one bookmark per school-teacher pair
  UNIQUE(school_account_id, teacher_id)
);

-- ----------------------------------------------------------------------------
-- School Payments Table
-- ----------------------------------------------------------------------------
CREATE TABLE school_payments (
  id BIGSERIAL PRIMARY KEY,
  school_account_id BIGINT NOT NULL REFERENCES school_accounts(id) ON DELETE CASCADE,

  -- Stripe Information
  stripe_payment_intent_id VARCHAR(255) UNIQUE NOT NULL,
  stripe_customer_id VARCHAR(255),

  -- Payment Details
  amount INTEGER NOT NULL, -- Amount in cents
  currency VARCHAR(3) NOT NULL DEFAULT 'CNY',
  status VARCHAR(50) NOT NULL DEFAULT 'pending', -- 'pending', 'succeeded', 'failed', 'refunded'
  payment_method VARCHAR(50),
  receipt_url TEXT,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- School accounts indexes
CREATE INDEX idx_school_accounts_user_id ON school_accounts(user_id);
CREATE INDEX idx_school_accounts_school_id ON school_accounts(school_id);
CREATE INDEX idx_school_accounts_city ON school_accounts(city);
CREATE INDEX idx_school_accounts_has_paid ON school_accounts(has_paid);
CREATE INDEX idx_school_accounts_status ON school_accounts(status);
CREATE INDEX idx_school_accounts_created_at ON school_accounts(created_at DESC);

-- School saved teachers indexes
CREATE INDEX idx_school_saved_teachers_school_account_id ON school_saved_teachers(school_account_id);
CREATE INDEX idx_school_saved_teachers_teacher_id ON school_saved_teachers(teacher_id);
CREATE INDEX idx_school_saved_teachers_created_at ON school_saved_teachers(created_at DESC);

-- School payments indexes
CREATE INDEX idx_school_payments_school_account_id ON school_payments(school_account_id);
CREATE INDEX idx_school_payments_stripe_payment_intent_id ON school_payments(stripe_payment_intent_id);
CREATE INDEX idx_school_payments_status ON school_payments(status);
CREATE INDEX idx_school_payments_created_at ON school_payments(created_at DESC);

-- Unique constraint for successful payments (one per school)
CREATE UNIQUE INDEX idx_school_payments_school_succeeded
  ON school_payments(school_account_id)
  WHERE status = 'succeeded';

-- ============================================================================
-- TRIGGERS FOR updated_at
-- ============================================================================

-- Apply trigger to school_accounts
CREATE TRIGGER update_school_accounts_updated_at BEFORE UPDATE ON school_accounts
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to school_payments
CREATE TRIGGER update_school_payments_updated_at BEFORE UPDATE ON school_payments
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all new tables
ALTER TABLE school_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_saved_teachers ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_payments ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- School Accounts Table RLS Policies
-- ----------------------------------------------------------------------------

-- School users can view their own account
CREATE POLICY "School users can view own account"
  ON school_accounts FOR SELECT
  USING (auth.uid() = user_id);

-- School users can update their own account
CREATE POLICY "School users can update own account"
  ON school_accounts FOR UPDATE
  USING (auth.uid() = user_id);

-- School users can insert their own account (during signup)
CREATE POLICY "School users can insert own account"
  ON school_accounts FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Admins can view all school accounts
CREATE POLICY "Admins can view all school accounts"
  ON school_accounts FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- Admins can manage all school accounts
CREATE POLICY "Admins can manage school accounts"
  ON school_accounts FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- School Saved Teachers Table RLS Policies
-- ----------------------------------------------------------------------------

-- Schools can view their own saved teachers
CREATE POLICY "Schools can view own saved teachers"
  ON school_saved_teachers FOR SELECT
  USING (
    school_account_id IN (
      SELECT id FROM school_accounts WHERE user_id = auth.uid()
    )
  );

-- Schools can manage their own saved teachers
CREATE POLICY "Schools can manage own saved teachers"
  ON school_saved_teachers FOR ALL
  USING (
    school_account_id IN (
      SELECT id FROM school_accounts WHERE user_id = auth.uid()
    )
  );

-- Admins can view all saved teachers
CREATE POLICY "Admins can view all saved teachers"
  ON school_saved_teachers FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ----------------------------------------------------------------------------
-- School Payments Table RLS Policies
-- ----------------------------------------------------------------------------

-- Schools can view their own payments
CREATE POLICY "Schools can view own payments"
  ON school_payments FOR SELECT
  USING (
    school_account_id IN (
      SELECT id FROM school_accounts WHERE user_id = auth.uid()
    )
  );

-- Admins can view all school payments
CREATE POLICY "Admins can view all school payments"
  ON school_payments FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM admin_users
      WHERE admin_users.id = auth.uid()
      AND admin_users.is_active = true
    )
  );

-- ============================================================================
-- UPDATE EXISTING RLS POLICIES
-- ============================================================================

-- Allow paid school accounts to view teachers (for browsing)
CREATE POLICY "Paid schools can view teachers"
  ON teachers FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM school_accounts
      WHERE school_accounts.user_id = auth.uid()
      AND school_accounts.is_active = true
    )
  );

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE school_accounts IS 'School user accounts for accessing teacher database';
COMMENT ON TABLE school_saved_teachers IS 'Bookmarked/saved teachers for school accounts';
COMMENT ON TABLE school_payments IS 'Payment records for school account access';

COMMENT ON COLUMN school_accounts.school_id IS 'Optional link to existing schools table';
COMMENT ON COLUMN school_accounts.annual_recruitment_volume IS 'How many teachers the school recruits annually';
COMMENT ON COLUMN school_accounts.has_paid IS 'Whether school has paid for full access (7500 RMB)';

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================

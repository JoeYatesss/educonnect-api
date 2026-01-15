-- Create enum for invoice request status
CREATE TYPE invoice_request_status AS ENUM ('pending', 'approved', 'rejected');

-- Create table for school invoice/manual payment requests
CREATE TABLE school_invoice_requests (
  id SERIAL PRIMARY KEY,
  school_account_id INTEGER NOT NULL REFERENCES school_accounts(id) ON DELETE CASCADE,
  company_name TEXT NOT NULL,
  billing_address TEXT NOT NULL,
  additional_notes TEXT,
  amount INTEGER NOT NULL DEFAULT 750000, -- Amount in cents (¥7,500)
  currency TEXT NOT NULL DEFAULT 'CNY',
  status invoice_request_status NOT NULL DEFAULT 'pending',
  admin_notes TEXT, -- Notes from admin when approving/rejecting
  reviewed_by TEXT, -- Admin email who reviewed
  reviewed_at TIMESTAMPTZ, -- When the request was reviewed
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_school_invoice_requests_school_id ON school_invoice_requests(school_account_id);
CREATE INDEX idx_school_invoice_requests_status ON school_invoice_requests(status);

-- Enable RLS
ALTER TABLE school_invoice_requests ENABLE ROW LEVEL SECURITY;

-- Policy: Schools can view their own invoice requests
CREATE POLICY "Schools can view own invoice requests"
  ON school_invoice_requests FOR SELECT
  USING (
    school_account_id IN (
      SELECT id FROM school_accounts WHERE user_id = auth.uid()
    )
  );

-- Policy: Schools can insert their own invoice requests
CREATE POLICY "Schools can create own invoice requests"
  ON school_invoice_requests FOR INSERT
  WITH CHECK (
    school_account_id IN (
      SELECT id FROM school_accounts WHERE user_id = auth.uid()
    )
  );

-- Trigger for updated_at
CREATE TRIGGER update_school_invoice_requests_updated_at
  BEFORE UPDATE ON school_invoice_requests
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

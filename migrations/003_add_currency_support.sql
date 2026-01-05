-- Migration: Add currency support for multi-currency payments
-- Date: 2026-01-05
-- Description: Add currency detection and preference fields to teachers table

-- Add currency-related fields to teachers table
ALTER TABLE teachers
ADD COLUMN detected_country VARCHAR(2),      -- ISO 3166-1 alpha-2 country code detected from IP
ADD COLUMN detected_currency VARCHAR(3),     -- Currency detected based on location (GBP/EUR/USD)
ADD COLUMN preferred_currency VARCHAR(3);    -- User's manually selected currency override

-- Add comments for documentation
COMMENT ON COLUMN teachers.detected_country IS 'ISO 3166-1 alpha-2 country code detected from IP';
COMMENT ON COLUMN teachers.detected_currency IS 'Currency detected based on user location (GBP, EUR, USD)';
COMMENT ON COLUMN teachers.preferred_currency IS 'User manually selected currency override';

-- Create indexes for performance
CREATE INDEX idx_teachers_preferred_currency ON teachers(preferred_currency);
CREATE INDEX idx_teachers_detected_country ON teachers(detected_country);

-- Set defaults for existing teachers (current GBP users)
UPDATE teachers SET
  detected_currency = 'GBP',
  preferred_currency = 'GBP'
WHERE detected_currency IS NULL;

-- Migration: 004_add_payment_constraints.sql
-- Purpose: Add database constraints to ensure data integrity for payment system
-- Date: 2026-01-05

-- 1. Ensure teacher can only have one successful payment
-- This prevents multiple "succeeded" payment records for the same teacher
CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_teacher_succeeded
ON payments(teacher_id, status)
WHERE status = 'succeeded';

-- 2. Add comment to document the has_paid column constraint
-- This is enforced at the application level, but documented here for clarity
COMMENT ON COLUMN teachers.has_paid IS
'Must be true if and only if a succeeded payment exists for this teacher. '
'Updated by webhook handler when checkout.session.completed event is received.';

-- 3. Add comment to document the payment_id relationship
COMMENT ON COLUMN teachers.payment_id IS
'Stripe payment intent ID (format: pi_xxx). Should match stripe_payment_intent_id in payments table. '
'Set when payment is successfully processed via Stripe webhook.';

-- 4. Add index to improve payment lookup performance
CREATE INDEX IF NOT EXISTS idx_teachers_payment_id ON teachers(payment_id);
CREATE INDEX IF NOT EXISTS idx_teachers_has_paid ON teachers(has_paid) WHERE has_paid = true;

-- 5. Add index to improve webhook processing performance
CREATE INDEX IF NOT EXISTS idx_payments_stripe_payment_intent_id ON payments(stripe_payment_intent_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

-- Note: We don't add a foreign key constraint from teachers.payment_id to payments.stripe_payment_intent_id
-- because the order of operations in the webhook handler creates the payment record first,
-- then updates the teacher record. A foreign key would require the payment to exist before
-- the teacher can reference it, which our current flow already ensures through application logic.

-- Verification queries (run after migration):
-- 1. Check for duplicate succeeded payments:
--    SELECT teacher_id, COUNT(*) FROM payments WHERE status = 'succeeded' GROUP BY teacher_id HAVING COUNT(*) > 1;
--
-- 2. Check for inconsistent has_paid status:
--    SELECT t.id, t.has_paid, COUNT(p.id) as payment_count
--    FROM teachers t
--    LEFT JOIN payments p ON t.id = p.teacher_id AND p.status = 'succeeded'
--    GROUP BY t.id, t.has_paid
--    HAVING (t.has_paid = true AND COUNT(p.id) = 0) OR (t.has_paid = false AND COUNT(p.id) > 0);

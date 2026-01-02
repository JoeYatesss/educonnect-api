# Database Migrations

This directory contains SQL migration files for the EduConnect database.

## Quick Setup

1. **Create a new Supabase project** at [supabase.com](https://supabase.com)
2. **Copy your Supabase credentials** (you'll need these later)
3. **Run the initial schema migration**

## Running Migrations

### Option 1: Supabase SQL Editor (Recommended for beginners)

1. Go to your Supabase project dashboard
2. Click on **SQL Editor** in the left sidebar
3. Click **New Query**
4. Copy the contents of `001_initial_schema.sql`
5. Paste into the editor
6. Click **Run** (or press Cmd/Ctrl + Enter)
7. Wait for completion (should take 10-30 seconds)
8. Check for any errors in the output

### Option 2: Supabase CLI (For developers)

```bash
# Install Supabase CLI
npm install -g supabase

# Login to Supabase
supabase login

# Link to your project
supabase link --project-ref your-project-ref

# Run migration
supabase db push

# Or apply specific migration
psql -h db.your-project.supabase.co -U postgres -d postgres -f migrations/001_initial_schema.sql
```

### Option 3: Direct PostgreSQL Connection

```bash
# Connect directly
psql "postgresql://postgres:[YOUR-PASSWORD]@db.your-project.supabase.co:5432/postgres"

# Run migration
\i /path/to/migrations/001_initial_schema.sql

# Exit
\q
```

## What Gets Created

### Tables (10 total):

1. **teachers** - Teacher profiles with payment status
2. **admin_users** - Admin accounts (linked to auth.users)
3. **schools** - School/institution profiles
4. **jobs** - Job postings
5. **teacher_school_matches** - Potential matches (from algorithm)
6. **teacher_school_applications** - Actual submissions to schools
7. **application_status_history** - Status change audit trail
8. **teacher_status_history** - Teacher status audit trail
9. **payments** - Stripe payment records
10. **job_interests** - Public job interest submissions

### Custom Types (Enums):

- `application_status` - 7-stage workflow status
- `admin_role` - Admin role types
- `school_type` - School categories

### Indexes (25 total):

All tables have proper indexes for:
- Foreign keys
- Commonly queried columns
- Sort columns (created_at, match_score, etc.)

### RLS Policies (22 total):

- ✅ Teachers can only view/update their own data
- ✅ Teachers CANNOT view schools table (anonymized via backend)
- ✅ Admins can view/manage all data
- ✅ Public can view active jobs

### Triggers (7 total):

- Auto-update `updated_at` timestamp on all relevant tables

## Post-Migration Setup

### 1. Create Storage Buckets

In Supabase Dashboard → Storage:

```
Bucket Name: cvs
- Public: No
- File size limit: 10MB
- Allowed MIME types: application/pdf, application/msword, application/vnd.openxmlformats-officedocument.wordprocessingml.document

Bucket Name: intro-videos
- Public: No
- File size limit: 100MB
- Allowed MIME types: video/mp4, video/quicktime

Bucket Name: headshot-photos
- Public: No
- File size limit: 10MB
- Allowed MIME types: image/jpeg, image/png
```

### 2. Set Up Storage Policies

For each bucket, add these policies in Supabase Dashboard → Storage → Policies:

**Upload Policy (Teachers can upload to own folder):**
```sql
-- Policy name: Teachers can upload own files
-- Allowed operation: INSERT
-- Target roles: authenticated

(bucket_id = 'cvs' OR bucket_id = 'intro-videos' OR bucket_id = 'headshot-photos')
AND auth.uid()::text = (storage.foldername(name))[1]
```

**Read Policy (Admins can read all):**
```sql
-- Policy name: Admins can read all files
-- Allowed operation: SELECT
-- Target roles: authenticated

(bucket_id = 'cvs' OR bucket_id = 'intro-videos' OR bucket_id = 'headshot-photos')
AND EXISTS (
  SELECT 1 FROM admin_users
  WHERE admin_users.id = auth.uid()
  AND admin_users.is_active = true
)
```

**Read Own Policy (Teachers can read own files):**
```sql
-- Policy name: Teachers can read own files
-- Allowed operation: SELECT
-- Target roles: authenticated

(bucket_id = 'cvs' OR bucket_id = 'intro-videos' OR bucket_id = 'headshot-photos')
AND auth.uid()::text = (storage.foldername(name))[1]
```

### 3. Create Your First Admin User

**Method 1: Via Supabase Dashboard**

1. Go to Authentication → Users
2. Click "Add user"
3. Enter email and password
4. Click "Create user"
5. Copy the user's UUID
6. Go to SQL Editor and run:

```sql
INSERT INTO admin_users (id, full_name, role, is_active)
VALUES (
  'paste-user-uuid-here',
  'Your Name',
  'master_admin',
  true
);
```

**Method 2: Via SQL (All at once)**

```sql
-- This will create both the auth user and admin record
-- Replace with your actual email and desired password

-- First, you need to create the user in Supabase Dashboard
-- Then link it to admin_users table with the UUID from auth.users
```

### 4. Configure Authentication

In Supabase Dashboard → Authentication → Settings:

**Email Auth:**
- ✅ Enable Email provider
- ✅ Confirm email: Enabled
- ✅ Double confirm email changes: Enabled

**Email Templates:**
- Customize "Confirm signup" template
- Customize "Reset password" template
- Use your domain (e.g., noreply@educonnect.com)

**Redirect URLs:**
- Add: `http://localhost:3000/auth/callback`
- Add: `https://yourdomain.com/auth/callback`

**JWT Settings:**
- JWT expiry: 3600 (1 hour)
- Note the JWT secret (needed for backend .env)

## Verification

### Check Tables Were Created

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

### Check RLS Is Enabled

```sql
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

### Check Indexes

```sql
SELECT
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
```

### Check Policies

```sql
SELECT
  schemaname,
  tablename,
  policyname,
  permissive,
  roles,
  cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
```

## Environment Variables

After setup, update your `.env` files:

**Backend (`educonnect-api/.env`):**
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

**Frontend (`educonnect-web/.env.local`):**
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

## Troubleshooting

### Error: "permission denied for schema public"
**Solution:** Make sure you're using the `postgres` user or have proper permissions.

### Error: "extension "uuid-ossp" does not exist"
**Solution:** Supabase enables this by default. If using another PostgreSQL, run:
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### RLS blocks all queries
**Solution:**
- For admin queries, use the **service role key** (backend only)
- For user queries, ensure JWT token is valid and included in request
- Test RLS with `SET ROLE authenticated;` in SQL editor

### Can't create admin user
**Solution:**
1. First create user in Authentication → Users
2. Then insert into admin_users table with the user's UUID
3. Make sure the UUID matches exactly

## Security Best Practices

1. ✅ **Never** use service role key in frontend
2. ✅ **Always** use anon key in frontend
3. ✅ **Enable** RLS on all tables
4. ✅ **Test** RLS policies before deploying
5. ✅ **Rotate** API keys regularly
6. ✅ **Monitor** auth logs for suspicious activity
7. ✅ **Limit** file upload sizes
8. ✅ **Validate** file types in storage policies

## Migration History

| Migration | Date | Description |
|-----------|------|-------------|
| 001_initial_schema | 2026-01-02 | Initial database setup with all tables, RLS, indexes, and triggers |

## Next Steps

1. ✅ Run migration
2. ✅ Create storage buckets
3. ✅ Set up storage policies
4. ✅ Create first admin user
5. ✅ Update environment variables
6. ⏳ Test authentication flow
7. ⏳ Test file uploads
8. ⏳ Seed sample data (optional)

---

**Need Help?**
- [Supabase Documentation](https://supabase.com/docs)
- [Supabase SQL Editor Guide](https://supabase.com/docs/guides/database/overview)
- [Row Level Security Guide](https://supabase.com/docs/guides/auth/row-level-security)

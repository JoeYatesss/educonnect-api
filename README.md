# EduConnect API (Backend)

FastAPI Python backend for the EduConnect teacher recruitment platform.

## Tech Stack

- **Framework:** FastAPI
- **Language:** Python 3.11+
- **Database:** Supabase (PostgreSQL)
- **Auth:** Supabase Auth (JWT)
- **Validation:** Pydantic
- **Payments:** Stripe
- **Email:** Resend

## Getting Started

### Prerequisites

- Python 3.11+
- Supabase account
- Stripe account
- Resend account (for emails)

### Installation

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy environment variables:
```bash
cp .env.example .env
```

4. Update `.env` with your credentials:
   - Supabase URL, service role key, and JWT secret
   - Stripe secret key and webhook secret
   - Resend API key
   - Allowed origins (CORS)

5. Run the development server:
```bash
uvicorn app.main:app --reload
```

6. Open [http://localhost:8000/docs](http://localhost:8000/docs) for API documentation

## Project Structure

```
app/
├── main.py                 # FastAPI app initialization
├── config.py              # Settings (Pydantic BaseSettings)
├── dependencies.py        # Dependency injection (auth, DB)
├── api/
│   └── v1/
│       └── endpoints/     # API endpoints
│           ├── auth.py
│           ├── teachers.py
│           ├── schools.py
│           ├── applications.py
│           ├── matching.py
│           ├── payments.py
│           └── admin.py
├── services/              # Business logic
│   ├── matching_service.py
│   ├── email_service.py
│   ├── storage_service.py
│   └── payment_service.py
├── models/                # Pydantic models (validation)
│   ├── teacher.py
│   ├── school.py
│   ├── application.py
│   └── payment.py
├── db/
│   ├── supabase.py       # Supabase client
│   └── repositories/     # Data access layer
│       ├── teacher_repo.py
│       ├── school_repo.py
│       └── application_repo.py
├── middleware/
│   ├── auth.py           # JWT validation
│   └── rate_limit.py     # Rate limiting
└── jobs/                 # Scheduled jobs
    └── matching_job.py
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/signup` - Teacher signup
- `POST /api/v1/auth/admin/login` - Admin login
- `POST /api/v1/auth/forgot-password` - Password reset

### Teachers
- `GET /api/v1/teachers/me` - Get current teacher profile
- `PATCH /api/v1/teachers/me` - Update profile
- `POST /api/v1/teachers/upload-cv` - Upload CV
- `GET /api/v1/teachers` - List all (admin only)

### Payments
- `POST /api/v1/payments/create-checkout-session` - Create Stripe Checkout
- `POST /api/v1/webhooks/stripe` - Stripe webhook handler

### Matching
- `POST /api/v1/matching/run` - Run matching algorithm (admin)
- `GET /api/v1/teachers/me/matches` - Get anonymous matches (teacher)
- `GET /api/v1/teachers/{id}/matches` - Get full matches (admin)

### Applications
- `POST /api/v1/applications` - Submit teacher to school(s) (admin)
- `GET /api/v1/applications/teacher/{id}` - Get applications (admin)
- `PATCH /api/v1/applications/{id}/status` - Update status (admin)

### Schools
- `GET /api/v1/schools` - List schools (admin only)
- `POST /api/v1/schools` - Create school (admin)
- `PUT /api/v1/schools/{id}` - Update school (admin)

See `/docs` for interactive API documentation.

## Available Scripts

- `uvicorn app.main:app --reload` - Start development server
- `pytest` - Run tests
- `pytest --cov` - Run tests with coverage

## Environment Variables

See `.env.example` for required environment variables.

**Security:** Never commit `.env` to version control.

## Security Features

- **Rate Limiting:** All endpoints rate-limited (configurable per endpoint)
- **JWT Validation:** All protected endpoints verify Supabase JWT
- **CORS:** Strict origin whitelist (no wildcards)
- **Input Validation:** Pydantic models validate all inputs
- **RLS:** Row Level Security on Supabase tables
- **Webhook Verification:** Stripe webhook signatures verified

## Deployment

### Railway (Recommended)

1. Push code to GitHub
2. Create new project in Railway
3. Add environment variables
4. Railway auto-deploys on push

### Docker

```bash
docker build -t educonnect-api .
docker run -p 8000:8000 --env-file .env educonnect-api
```

## Database Setup

1. Create new Supabase project
2. Run migration scripts in `app/db/migrations/`
3. Set up Row Level Security policies
4. Create admin user in auth.users table

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_teachers.py
```

## Matching Algorithm

The matching algorithm scores teacher-school compatibility based on:
- Location preference (35%)
- Subject specialty (25%)
- Age group (20%)
- Experience level (15%)
- Chinese requirement (5%)

Results are saved to `teacher_school_matches` table.

## Learn More

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Supabase Python Documentation](https://supabase.com/docs/reference/python)
- [Stripe Python Documentation](https://stripe.com/docs/api/python)

from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, teachers, payments, webhooks, matching, schools,
    applications, signup, blog, jobs, admin,
    school_signup, school_accounts, school_payments,
    school_jobs, school_interview_selections
)

api_router = APIRouter()

# Teacher/General routes
api_router.include_router(signup.router, prefix="/signup", tags=["signup"])
api_router.include_router(school_signup.router, prefix="/school-signup", tags=["school-signup"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(teachers.router, prefix="/teachers", tags=["teachers"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(matching.router, prefix="/matching", tags=["matching"])
api_router.include_router(schools.router, prefix="/schools", tags=["schools"])
api_router.include_router(applications.router, prefix="/applications", tags=["applications"])
api_router.include_router(blog.router, prefix="/blog", tags=["blog"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

# School account routes
api_router.include_router(school_signup.router, prefix="/school-signup", tags=["school-signup"])
api_router.include_router(school_accounts.router, prefix="/school-accounts", tags=["school-accounts"])
api_router.include_router(school_payments.router, prefix="/school-payments", tags=["school-payments"])
api_router.include_router(school_jobs.router, prefix="/school-jobs", tags=["school-jobs"])
api_router.include_router(school_interview_selections.router, prefix="/school-selections", tags=["school-selections"])

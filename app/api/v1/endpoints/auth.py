from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr
from app.dependencies import get_current_user
from app.db.supabase import get_supabase_client
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


class CheckEmailRequest(BaseModel):
    email: EmailStr


@router.post("/check-email-status")
@limiter.limit("30/minute")
async def check_email_status(request: Request, data: CheckEmailRequest):
    """
    Check if an email exists in our system (teachers, admin_users, or school_accounts).
    Returns whether the account exists and if email is confirmed.
    No authentication required - used for login flow.
    """
    supabase = get_supabase_client()
    email = data.email.lower()

    # Check teachers table
    try:
        teacher = supabase.table("teachers").select("id, email").eq("email", email).single().execute()
        if teacher.data:
            return {"exists": True, "confirmed": True, "account_type": "teacher"}
    except Exception:
        pass

    # Check admin_users table
    try:
        admin = supabase.table("admin_users").select("id, email").eq("email", email).single().execute()
        if admin.data:
            return {"exists": True, "confirmed": True, "account_type": "admin"}
    except Exception:
        pass

    # Check school_accounts table
    try:
        school = supabase.table("school_accounts").select("id, contact_email").eq("contact_email", email).single().execute()
        if school.data:
            return {"exists": True, "confirmed": True, "account_type": "school"}
    except Exception:
        pass

    return {"exists": False, "confirmed": None, "account_type": None}


@router.get("/me")
@limiter.limit("300/minute")  # Increased for development
async def get_current_user_profile(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Get current user's profile and role.
    Returns user info with teacher/admin profile if they exist.
    Used by middleware for route protection and role checking.
    """
    supabase = get_supabase_client()

    result = {
        "user": current_user,
        "teacher": None,
        "admin": None,
        "school": None,
        "role": None,  # Will be 'teacher', 'admin', 'school', or None
    }

    # Try to get teacher profile
    try:
        from app.models.teacher import TeacherResponse

        teacher_response = supabase.table("teachers").select("*").eq("user_id", current_user["id"]).single().execute()
        if teacher_response.data:
            # Calculate profile completeness
            teacher_response.data["profile_completeness"] = TeacherResponse.calculate_profile_completeness(teacher_response.data)
            result["teacher"] = teacher_response.data
            result["role"] = "teacher"
            return result
    except Exception:
        pass  # User is not a teacher

    # Try to get admin profile
    try:
        admin_response = supabase.table("admin_users").select("*").eq("id", current_user["id"]).single().execute()
        if admin_response.data:
            result["admin"] = admin_response.data
            result["role"] = "admin"
            return result
    except Exception:
        pass  # User is not an admin

    # Try to get school account
    try:
        school_response = supabase.table("school_accounts").select("*").eq("user_id", current_user["id"]).single().execute()
        if school_response.data:
            result["school"] = school_response.data
            result["role"] = "school"
            return result
    except Exception:
        pass  # User is not a school account

    return result

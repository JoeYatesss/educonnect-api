from fastapi import APIRouter, Depends, Request
from app.dependencies import get_current_user
from app.db.supabase import get_supabase_client
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/me")
@limiter.limit("30/minute")
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
        "role": None,  # Will be 'teacher', 'admin', or None
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
    except Exception:
        pass  # User is not a teacher

    # Try to get admin profile (only if not a teacher)
    if not result["teacher"]:
        try:
            admin_response = supabase.table("admin_users").select("*").eq("id", current_user["id"]).single().execute()
            if admin_response.data:
                result["admin"] = admin_response.data
                result["role"] = "admin"
        except Exception:
            pass  # User is not an admin

    return result

from fastapi import APIRouter, Depends, Request, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from app.dependencies import get_current_user
from app.db.supabase import get_supabase_client
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


# Request/Response Models
class CheckEmailRequest(BaseModel):
    email: EmailStr


class EmailStatusResponse(BaseModel):
    exists: bool
    confirmed: Optional[bool] = None


class ResendConfirmationRequest(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str


@router.get("/me")
@limiter.limit("300/minute")  # Increased for development
async def get_current_user_profile(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Get current user's profile and role.
    Returns user info with teacher/admin/school profile if they exist.
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

    # Try to get school profile (only if not a teacher or admin)
    if not result["teacher"] and not result["admin"]:
        try:
            school_response = supabase.table("school_accounts").select("*").eq("user_id", current_user["id"]).single().execute()
            if school_response.data:
                result["school"] = school_response.data
                result["role"] = "school"
        except Exception:
            pass  # User is not a school

    return result


@router.post("/check-email-status", response_model=EmailStatusResponse)
@limiter.limit("10/hour")
async def check_email_status(request: Request, data: CheckEmailRequest):
    """
    Check if an email exists in the system and its confirmation status.
    Rate limited to 10/hour per IP to prevent email enumeration attacks.

    This endpoint enables better UX by allowing the frontend to distinguish
    between "wrong password" and "no account exists" scenarios.
    """
    supabase = get_supabase_client()

    try:
        # Use admin API to list users and find by email
        users_response = supabase.auth.admin.list_users()
        user = next(
            (u for u in users_response.users if u.email == data.email),
            None
        )

        if not user:
            return EmailStatusResponse(exists=False)

        return EmailStatusResponse(
            exists=True,
            confirmed=user.email_confirmed_at is not None
        )
    except Exception as e:
        logger.error(f"Failed to check email status: {e}")
        # On error, return exists=True to avoid leaking info
        return EmailStatusResponse(exists=True, confirmed=None)


@router.post("/resend-confirmation", response_model=MessageResponse)
@limiter.limit("3/hour")
async def resend_confirmation_email(request: Request, data: ResendConfirmationRequest):
    """
    Resend email confirmation for unconfirmed users.
    Rate limited to 3/hour per IP to prevent spam abuse.

    Uses Supabase's resend functionality to trigger a new confirmation email.
    """
    supabase = get_supabase_client()

    try:
        # First check if user exists and is unconfirmed
        users_response = supabase.auth.admin.list_users()
        user = next(
            (u for u in users_response.users if u.email == data.email),
            None
        )

        if not user:
            # Don't reveal whether email exists for security
            return MessageResponse(
                message="If an account exists with this email, a confirmation link has been sent."
            )

        if user.email_confirmed_at:
            return MessageResponse(
                message="Email is already confirmed. Please try logging in."
            )

        # Resend confirmation email using Supabase
        supabase.auth.resend(type="signup", email=data.email)

        return MessageResponse(message="Confirmation email sent. Please check your inbox.")
    except Exception as e:
        logger.error(f"Failed to resend confirmation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send confirmation email. Please try again later."
        )

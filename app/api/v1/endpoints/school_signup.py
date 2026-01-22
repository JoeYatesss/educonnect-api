from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field
from app.db.supabase import get_supabase_client
from app.middleware.rate_limit import limiter
from app.services.email_service import EmailService
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class SchoolSignupRequest(BaseModel):
    """School account creation during signup - no auth required"""
    user_id: str  # Supabase auth user ID
    school_name: str = Field(..., min_length=1, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    contact_email: EmailStr
    wechat_id: Optional[str] = Field(None, max_length=100)
    annual_recruitment_volume: Optional[str] = None  # "1-5", "6-10", "11-20", "20+"


@router.post("/create-school-account", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def create_school_account_signup(
    request: Request,
    data: SchoolSignupRequest
):
    """
    Create school account during signup (no JWT required)

    This endpoint is called immediately after Supabase auth signup,
    before email verification. It verifies the user exists in Supabase auth
    before creating the school account.
    """
    supabase = get_supabase_client()

    # Verify the user exists in Supabase auth (prevents fake user IDs)
    try:
        auth_user = supabase.auth.admin.get_user_by_id(data.user_id)
        if not auth_user.user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in authentication system"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user ID: {str(e)}"
        )

    # Check if school account already exists for this user
    existing = supabase.table("school_accounts").select("id").eq("user_id", data.user_id).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School account already exists for this user"
        )

    # Check if this user already has a teacher profile (can't be both)
    existing_teacher = supabase.table("teachers").select("id").eq("user_id", data.user_id).execute()
    if existing_teacher.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account is registered as a teacher. Please use a different email for school registration."
        )

    # Create school account
    school_data = {
        "user_id": data.user_id,
        "school_name": data.school_name,
        "city": data.city,
        "contact_email": data.contact_email,
        "wechat_id": data.wechat_id,
        "annual_recruitment_volume": data.annual_recruitment_volume,
        "status": "pending",
        "is_active": True,
    }

    response = supabase.table("school_accounts").insert(school_data).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create school account"
        )

    school = response.data[0]

    # Send notification email to team (don't fail signup if email fails)
    try:
        EmailService.send_school_signup_notification(
            school_name=data.school_name,
            city=data.city,
            contact_email=data.contact_email,
            wechat_id=data.wechat_id,
            recruitment_volume=data.annual_recruitment_volume
        )
        logger.info(f"School signup notification sent for: {data.school_name}")
    except Exception as e:
        logger.error(f"Failed to send school signup notification email: {str(e)}")

    return {
        "message": "School account created successfully",
        "school": school
    }

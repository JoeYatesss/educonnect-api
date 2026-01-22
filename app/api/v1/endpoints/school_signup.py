from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from app.db.supabase import get_supabase_client
from app.middleware.rate_limit import limiter
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class SchoolSignupRequest(BaseModel):
    """School account creation during signup - no auth required"""
    user_id: str  # Supabase auth user ID
    school_name: str
    city: str
    contact_name: str
    contact_email: EmailStr
    contact_phone: Optional[str] = None
    wechat_id: Optional[str] = None
    annual_recruitment_volume: Optional[str] = None


@router.post("/create-school-account", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def create_school_account(
    request: Request,
    data: SchoolSignupRequest
):
    """
    Create school account during signup (no JWT required)

    This endpoint is called immediately after Supabase auth signup,
    before email verification. It verifies the user exists in Supabase auth
    before creating the account.
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

    # Check if school account already exists
    existing = supabase.table("school_accounts").select("id").eq("user_id", data.user_id).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School account already exists"
        )

    # Create school account
    account_data = {
        "user_id": data.user_id,
        "school_name": data.school_name,
        "city": data.city,
        "contact_name": data.contact_name,
        "contact_email": data.contact_email,
        "contact_phone": data.contact_phone,
        "wechat_id": data.wechat_id,
        "annual_recruitment_volume": data.annual_recruitment_volume,
        "status": "pending",
        "has_paid": False,
        "is_active": True,
    }

    response = supabase.table("school_accounts").insert(account_data).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create school account"
        )

    account = response.data[0]

    logger.info(f"School account created: {data.school_name} ({data.contact_email})")

    return {
        "message": "School account created successfully",
        "school_account": account
    }

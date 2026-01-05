from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, EmailStr
from app.db.supabase import get_supabase_client
from app.services.matching_service import MatchingService
from typing import Optional
import logging

logger = logging.getLogger(__name__)


router = APIRouter()


class SignupTeacherRequest(BaseModel):
    """Teacher profile creation during signup - no auth required"""
    user_id: str  # Supabase auth user ID
    first_name: str
    last_name: str
    email: EmailStr
    preferred_location: str
    subject_specialty: str
    preferred_age_group: str
    linkedin: Optional[str] = None


@router.post("/create-teacher-profile", status_code=status.HTTP_201_CREATED)
async def create_teacher_profile_signup(
    data: SignupTeacherRequest,
    background_tasks: BackgroundTasks
):
    """
    Create teacher profile during signup (no JWT required)

    This endpoint is called immediately after Supabase auth signup,
    before email verification. It verifies the user exists in Supabase auth
    before creating the profile.

    Automatically triggers matching algorithm in background after creation.
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user ID: {str(e)}"
        )

    # Check if teacher profile already exists
    existing = supabase.table("teachers").select("id").eq("user_id", data.user_id).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Teacher profile already exists"
        )

    # Create teacher profile
    teacher_data = {
        "user_id": data.user_id,
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "preferred_location": data.preferred_location,
        "subject_specialty": data.subject_specialty,
        "preferred_age_group": data.preferred_age_group,
        "linkedin": data.linkedin,
        "status": "pending",
    }

    response = supabase.table("teachers").insert(teacher_data).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create teacher profile"
        )

    teacher = response.data[0]

    # Trigger matching algorithm in background
    background_tasks.add_task(
        _run_matching_for_teacher,
        teacher["id"]
    )

    return {
        "message": "Teacher profile created successfully",
        "teacher": teacher
    }


def _run_matching_for_teacher(teacher_id: int):
    """Background task wrapper for matching"""
    try:
        matches = MatchingService.run_matching_for_teacher(teacher_id)
        logger.info(f"Auto-matching completed for teacher {teacher_id}: {len(matches)} matches found")
    except Exception as e:
        logger.error(f"Auto-matching failed for teacher {teacher_id}: {str(e)}")

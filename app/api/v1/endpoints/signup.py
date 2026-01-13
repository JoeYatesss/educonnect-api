from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field
from app.db.supabase import get_supabase_client
from app.middleware.rate_limit import limiter
from app.services.email_service import EmailService
from app.services.storage_service import StorageService
from typing import Optional, List
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
@limiter.limit("10/hour")
async def create_teacher_profile_signup(
    request: Request,
    data: SignupTeacherRequest
):
    """
    Create teacher profile during signup (no JWT required)

    This endpoint is called immediately after Supabase auth signup,
    before email verification. It verifies the user exists in Supabase auth
    before creating the profile.

    Matching is triggered later when payment is completed.
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

    # Send notification email to team (don't fail signup if email fails)
    try:
        EmailService.send_teacher_signup_notification(
            teacher_name=f"{data.first_name} {data.last_name}",
            teacher_email=data.email,
            preferred_location=data.preferred_location,
            subject_specialty=data.subject_specialty,
            preferred_age_group=data.preferred_age_group,
            linkedin=data.linkedin
        )
        logger.info(f"Signup notification sent for teacher: {data.email}")
    except Exception as e:
        logger.error(f"Failed to send signup notification email: {str(e)}")

    return {
        "message": "Teacher profile created successfully",
        "teacher": teacher
    }


class SignupWithFilesRequest(BaseModel):
    """Teacher profile creation with file upload support - v2 endpoint"""
    user_id: str  # Supabase auth user ID
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    preferred_locations: List[str] = Field(..., min_length=1)  # Array of cities
    subject_specialties: List[str] = Field(..., min_length=1)  # Array of subjects
    preferred_age_groups: List[str] = Field(..., min_length=1)  # Array of age groups
    linkedin: Optional[str] = None
    # File extensions for generating upload URLs
    cv_extension: str = Field(..., pattern="^(pdf|doc|docx)$")
    headshot_extension: str = Field(..., pattern="^(jpg|jpeg|png)$")
    video_extension: str = Field(..., pattern="^(mp4|mov)$")


class SignupWithFilesResponse(BaseModel):
    """Response with teacher data and presigned upload URLs"""
    message: str
    teacher_id: int
    # CV upload info
    cv_bucket: str
    cv_path: str
    cv_token: str
    # Headshot upload info
    headshot_bucket: str
    headshot_path: str
    headshot_token: str
    # Video upload info
    video_bucket: str
    video_path: str
    video_token: str


@router.post("/create-teacher-profile-v2", status_code=status.HTTP_201_CREATED, response_model=SignupWithFilesResponse)
@limiter.limit("10/hour")
async def create_teacher_profile_with_files(
    request: Request,
    data: SignupWithFilesRequest
):
    """
    Create teacher profile during signup with presigned upload URLs (v2).

    This endpoint:
    1. Verifies the user exists in Supabase auth
    2. Creates the teacher profile with multi-select preferences
    3. Generates presigned upload URLs for CV, headshot, and video
    4. Returns URLs for direct file upload to storage

    After calling this endpoint, the frontend should:
    1. Upload files directly to the presigned URLs
    2. Call /confirm-file-uploads to mark files as uploaded
    """
    supabase = get_supabase_client()

    # Verify the user exists in Supabase auth
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

    # Check if teacher profile already exists
    existing = supabase.table("teachers").select("id").eq("user_id", data.user_id).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Teacher profile already exists"
        )

    # Convert arrays to comma-separated strings for database storage
    preferred_location = ", ".join(data.preferred_locations)
    subject_specialty = ", ".join(data.subject_specialties)
    preferred_age_group = ", ".join(data.preferred_age_groups)

    # Create teacher profile
    teacher_data = {
        "user_id": data.user_id,
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "preferred_location": preferred_location,
        "subject_specialty": subject_specialty,
        "preferred_age_group": preferred_age_group,
        "linkedin": data.linkedin,
        "status": "pending",
    }

    logger.info(f"[Signup V2] Inserting teacher data: {teacher_data}")
    response = supabase.table("teachers").insert(teacher_data).execute()
    logger.info(f"[Signup V2] Insert response: {response}")

    if not response.data:
        logger.error(f"[Signup V2] Insert failed - no data returned")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create teacher profile"
        )

    teacher = response.data[0]
    teacher_id = teacher["id"]
    logger.info(f"[Signup V2] Teacher created with ID: {teacher_id}")

    # Generate presigned upload URLs
    try:
        upload_urls = StorageService.generate_signup_upload_urls(
            teacher_id=teacher_id,
            cv_extension=data.cv_extension,
            headshot_extension=data.headshot_extension,
            video_extension=data.video_extension
        )
    except Exception as e:
        logger.error(f"Failed to generate upload URLs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate file upload URLs"
        )

    # Send notification email to team
    try:
        EmailService.send_teacher_signup_notification(
            teacher_name=f"{data.first_name} {data.last_name}",
            teacher_email=data.email,
            preferred_location=preferred_location,
            subject_specialty=subject_specialty,
            preferred_age_group=preferred_age_group,
            linkedin=data.linkedin
        )
        logger.info(f"Signup notification sent for teacher: {data.email}")
    except Exception as e:
        logger.error(f"Failed to send signup notification email: {str(e)}")

    return SignupWithFilesResponse(
        message="Teacher profile created successfully. Please upload files using the provided tokens.",
        teacher_id=teacher_id,
        cv_bucket=upload_urls["cv"]["bucket"],
        cv_path=upload_urls["cv"]["path"],
        cv_token=upload_urls["cv"]["token"],
        headshot_bucket=upload_urls["headshot"]["bucket"],
        headshot_path=upload_urls["headshot"]["path"],
        headshot_token=upload_urls["headshot"]["token"],
        video_bucket=upload_urls["video"]["bucket"],
        video_path=upload_urls["video"]["path"],
        video_token=upload_urls["video"]["token"]
    )


class ConfirmFileUploadsRequest(BaseModel):
    """Request to confirm files have been uploaded"""
    user_id: str
    cv_path: str
    headshot_path: str
    video_path: str


@router.post("/confirm-file-uploads", status_code=status.HTTP_200_OK)
@limiter.limit("10/hour")
async def confirm_file_uploads(
    request: Request,
    data: ConfirmFileUploadsRequest
):
    """
    Confirm that files have been uploaded to storage.

    This endpoint updates the teacher record with the file paths
    after successful upload to presigned URLs.
    """
    supabase = get_supabase_client()

    # Get teacher by user_id
    teacher_result = supabase.table("teachers").select("id").eq("user_id", data.user_id).execute()

    if not teacher_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher profile not found"
        )

    teacher_id = teacher_result.data[0]["id"]

    # Update teacher record with file paths
    update_data = {
        "cv_path": data.cv_path,
        "headshot_photo_path": data.headshot_path,
        "intro_video_path": data.video_path,
    }

    response = supabase.table("teachers").update(update_data).eq("id", teacher_id).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update teacher profile with file paths"
        )

    logger.info(f"File uploads confirmed for teacher {teacher_id}")

    return {
        "message": "File uploads confirmed successfully",
        "teacher_id": teacher_id
    }

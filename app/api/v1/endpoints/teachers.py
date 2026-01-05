from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request, BackgroundTasks
from app.models.teacher import TeacherCreate, TeacherUpdate, TeacherResponse
from app.dependencies import get_current_user, get_current_teacher, get_current_admin
from app.db.supabase import get_supabase_client
from app.services.storage_service import StorageService
from app.services.matching_service import MatchingService
from app.middleware.rate_limit import limiter
from typing import List
import logging

logger = logging.getLogger(__name__)

# Fields that affect matching - if updated, re-run matching algorithm
PREFERENCE_FIELDS = {'subject_specialty', 'preferred_location', 'preferred_age_group', 'years_experience'}


router = APIRouter()


@router.post("/", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
async def create_teacher(
    teacher: TeacherCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new teacher profile
    Called after successful signup
    """
    supabase = get_supabase_client()

    # Check if teacher already exists
    existing = supabase.table("teachers").select("id").eq("user_id", current_user["id"]).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Teacher profile already exists"
        )

    # Create teacher profile
    teacher_data = {
        "user_id": current_user["id"],
        "first_name": teacher.first_name,
        "last_name": teacher.last_name,
        "email": teacher.email,
        "preferred_location": teacher.preferred_location,
        "subject_specialty": teacher.subject_specialty,
        "preferred_age_group": teacher.preferred_age_group,
        "linkedin": teacher.linkedin,
        "status": "pending",  # Initial status
    }

    response = supabase.table("teachers").insert(teacher_data).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create teacher profile"
        )

    return response.data[0]


@router.get("/", response_model=List[TeacherResponse])
async def list_all_teachers(
    admin: dict = Depends(get_current_admin)
):
    """
    Get all teachers (admin only)
    Returns list of all teacher profiles with calculated completeness
    """
    supabase = get_supabase_client()
    from app.models.teacher import TeacherResponse

    response = supabase.table("teachers").select("*").order("created_at", desc=True).execute()

    # Calculate profile completeness for each teacher
    teachers = response.data or []
    for teacher in teachers:
        teacher["profile_completeness"] = TeacherResponse.calculate_profile_completeness(teacher)

    return teachers


@router.get("/me", response_model=TeacherResponse)
async def get_current_teacher_profile(
    teacher: dict = Depends(get_current_teacher)
):
    """
    Get current teacher's profile with calculated completeness percentage
    """
    from app.models.teacher import TeacherResponse

    # Calculate profile completeness
    teacher["profile_completeness"] = TeacherResponse.calculate_profile_completeness(teacher)

    return teacher


@router.get("/me/stats")
async def get_dashboard_stats(
    teacher: dict = Depends(get_current_teacher)
):
    """
    Get dashboard statistics for current teacher
    Returns match count, application count, profile completeness
    """
    supabase = get_supabase_client()
    from app.models.teacher import TeacherResponse

    # Count matches (preview count for unpaid, real count for paid)
    match_count = 0
    if teacher.get("has_paid"):
        matches = supabase.table("teacher_school_matches")\
            .select("id", count="exact")\
            .eq("teacher_id", teacher["id"])\
            .execute()
        match_count = matches.count or 0
    else:
        # For unpaid users, show preview count of 3
        match_count = 3

    # Count applications
    apps = supabase.table("teacher_school_applications")\
        .select("id", count="exact")\
        .eq("teacher_id", teacher["id"])\
        .execute()
    app_count = apps.count or 0

    # Calculate profile completeness
    profile_completeness = TeacherResponse.calculate_profile_completeness(teacher)

    return {
        "match_count": match_count,
        "application_count": app_count,
        "profile_completeness": profile_completeness,
        "has_paid": teacher.get("has_paid", False)
    }


@router.get("/me/files")
async def get_teacher_files(
    teacher: dict = Depends(get_current_teacher)
):
    """
    Get signed URLs for teacher's uploaded files
    Returns URLs that expire in 1 hour
    """
    from app.services.storage_service import StorageService

    files = {
        "cv_url": None,
        "cv_path": teacher.get("cv_path"),
        "headshot_url": None,
        "headshot_path": teacher.get("headshot_photo_path"),
        "video_url": None,
        "video_path": teacher.get("intro_video_path"),
    }

    # Generate signed URLs for uploaded files
    try:
        if teacher.get("cv_path"):
            files["cv_url"] = StorageService.get_teacher_cv_url(
                teacher["id"],
                teacher["cv_path"]
            )
    except Exception as e:
        print(f"Error getting CV URL: {e}")

    try:
        if teacher.get("headshot_photo_path"):
            files["headshot_url"] = StorageService.get_teacher_headshot_url(
                teacher["id"],
                teacher["headshot_photo_path"]
            )
    except Exception as e:
        print(f"Error getting headshot URL: {e}")

    try:
        if teacher.get("intro_video_path"):
            files["video_url"] = StorageService.get_teacher_video_url(
                teacher["id"],
                teacher["intro_video_path"]
            )
    except Exception as e:
        print(f"Error getting video URL: {e}")

    return files


@router.get("/download/cv")
async def download_cv(teacher: dict = Depends(get_current_teacher)):
    """Redirect to signed URL for CV download"""
    from app.services.storage_service import StorageService
    from fastapi.responses import RedirectResponse

    if not teacher.get("cv_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )

    try:
        signed_url = StorageService.get_teacher_cv_url(
            teacher["id"],
            teacher["cv_path"]
        )
        return RedirectResponse(url=signed_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get CV: {str(e)}"
        )


@router.get("/download/headshot")
async def download_headshot(teacher: dict = Depends(get_current_teacher)):
    """Redirect to signed URL for headshot download"""
    from app.services.storage_service import StorageService
    from fastapi.responses import RedirectResponse

    if not teacher.get("headshot_photo_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Headshot not found"
        )

    try:
        signed_url = StorageService.get_teacher_headshot_url(
            teacher["id"],
            teacher["headshot_photo_path"]
        )
        return RedirectResponse(url=signed_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get headshot: {str(e)}"
        )


@router.get("/download/video")
async def download_video(teacher: dict = Depends(get_current_teacher)):
    """Redirect to signed URL for video download"""
    from app.services.storage_service import StorageService
    from fastapi.responses import RedirectResponse

    if not teacher.get("intro_video_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )

    try:
        signed_url = StorageService.get_teacher_video_url(
            teacher["id"],
            teacher["intro_video_path"]
        )
        return RedirectResponse(url=signed_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video: {str(e)}"
        )


@router.patch("/me", response_model=TeacherResponse)
async def update_teacher_profile(
    update_data: TeacherUpdate,
    teacher: dict = Depends(get_current_teacher),
    background_tasks: BackgroundTasks = None
):
    """
    Update current teacher's profile.
    Automatically re-runs matching if preference fields are updated.
    """
    supabase = get_supabase_client()

    # Only update fields that are provided
    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        return teacher

    response = supabase.table("teachers").update(update_dict).eq("id", teacher["id"]).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update teacher profile"
        )

    # Check if any preference fields were updated - if so, re-run matching
    updated_preferences = set(update_dict.keys()) & PREFERENCE_FIELDS
    if updated_preferences and background_tasks:
        logger.info(f"Teacher {teacher['id']} updated preferences: {updated_preferences}, triggering re-match")
        background_tasks.add_task(
            _run_matching_for_teacher,
            teacher["id"]
        )

    return response.data[0]


def _run_matching_for_teacher(teacher_id: int):
    """Background task wrapper for matching"""
    try:
        matches = MatchingService.run_matching_for_teacher(teacher_id)
        logger.info(f"Auto-matching completed for teacher {teacher_id}: {len(matches)} matches found")
    except Exception as e:
        logger.error(f"Auto-matching failed for teacher {teacher_id}: {str(e)}")


@router.post("/upload-cv")
@limiter.limit("10/hour")
async def upload_cv(
    request: Request,
    file: UploadFile = File(...),
    teacher: dict = Depends(get_current_teacher)
):
    """
    Upload teacher CV (PDF, DOC, DOCX only, max 10MB)
    Rate limited to 10 uploads per hour
    """
    # Validate file type
    allowed_extensions = ['pdf', 'doc', 'docx']
    file_extension = file.filename.split('.')[-1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Validate file size (10MB)
    file_data = await file.read()
    file_size_mb = len(file_data) / (1024 * 1024)

    if file_size_mb > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 10MB"
        )

    try:
        # Upload to storage
        file_path = StorageService.upload_teacher_cv(
            teacher["id"],
            file_data,
            file.filename
        )

        # Update teacher record
        supabase = get_supabase_client()
        response = supabase.table("teachers").update({
            "cv_path": file_path
        }).eq("id", teacher["id"]).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update teacher record"
            )

        return {
            "message": "CV uploaded successfully",
            "file_path": file_path
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.post("/upload-video")
@limiter.limit("5/hour")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    teacher: dict = Depends(get_current_teacher)
):
    """
    Upload teacher intro video (MP4, MOV only, max 100MB)
    Rate limited to 5 uploads per hour
    """
    # Validate file type
    allowed_extensions = ['mp4', 'mov']
    file_extension = file.filename.split('.')[-1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Validate file size (100MB)
    file_data = await file.read()
    file_size_mb = len(file_data) / (1024 * 1024)

    if file_size_mb > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 100MB"
        )

    try:
        # Upload to storage
        file_path = StorageService.upload_teacher_video(
            teacher["id"],
            file_data,
            file.filename
        )

        # Update teacher record
        supabase = get_supabase_client()
        response = supabase.table("teachers").update({
            "intro_video_path": file_path
        }).eq("id", teacher["id"]).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update teacher record"
            )

        return {
            "message": "Video uploaded successfully",
            "file_path": file_path
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.post("/upload-headshot")
@limiter.limit("10/hour")
async def upload_headshot(
    request: Request,
    file: UploadFile = File(...),
    teacher: dict = Depends(get_current_teacher)
):
    """
    Upload teacher headshot photo (JPG, PNG only, max 10MB)
    Rate limited to 10 uploads per hour
    """
    # Validate file type
    allowed_extensions = ['jpg', 'jpeg', 'png']
    file_extension = file.filename.split('.')[-1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Validate file size (10MB)
    file_data = await file.read()
    file_size_mb = len(file_data) / (1024 * 1024)

    if file_size_mb > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 10MB"
        )

    try:
        # Upload to storage
        file_path = StorageService.upload_teacher_headshot(
            teacher["id"],
            file_data,
            file.filename
        )

        # Update teacher record
        supabase = get_supabase_client()
        response = supabase.table("teachers").update({
            "headshot_photo_path": file_path
        }).eq("id", teacher["id"]).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update teacher record"
            )

        return {
            "message": "Headshot uploaded successfully",
            "file_path": file_path
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )

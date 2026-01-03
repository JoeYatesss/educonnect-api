from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from app.models.teacher import TeacherCreate, TeacherUpdate, TeacherResponse
from app.dependencies import get_current_user, get_current_teacher
from app.db.supabase import get_supabase_client
from app.services.storage_service import StorageService
from app.middleware.rate_limit import limiter


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


@router.patch("/me", response_model=TeacherResponse)
async def update_teacher_profile(
    update_data: TeacherUpdate,
    teacher: dict = Depends(get_current_teacher)
):
    """
    Update current teacher's profile
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

    return response.data[0]


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

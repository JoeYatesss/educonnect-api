from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies import get_current_admin
from app.db.supabase import get_supabase_client
from app.services.storage_service import StorageService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats")
async def get_admin_stats(
    admin: dict = Depends(get_current_admin)
):
    """
    Get dashboard statistics for admin overview
    Returns counts of teachers, schools, applications, etc.
    """
    supabase = get_supabase_client()

    try:
        # Get total teachers count
        teachers_response = supabase.table("teachers").select("id", count="exact").execute()
        total_teachers = teachers_response.count or 0

        # Get paid teachers count
        paid_teachers_response = supabase.table("teachers").select("id", count="exact").eq("has_paid", True).execute()
        paid_teachers = paid_teachers_response.count or 0

        # Get active applications (not placed or declined)
        active_apps_response = supabase.table("teacher_school_applications").select("id", count="exact").not_.in_("status", ["placed", "declined"]).execute()
        active_applications = active_apps_response.count or 0

        # Get placed teachers count
        placed_response = supabase.table("teacher_school_applications").select("id", count="exact").eq("status", "placed").execute()
        placed_teachers = placed_response.count or 0

        # Get total schools count
        schools_response = supabase.table("schools").select("id", count="exact").execute()
        total_schools = schools_response.count or 0

        # Get total jobs count
        jobs_response = supabase.table("jobs").select("id", count="exact").execute()
        total_jobs = jobs_response.count or 0

        return {
            "total_teachers": total_teachers,
            "paid_teachers": paid_teachers,
            "active_applications": active_applications,
            "placed_teachers": placed_teachers,
            "total_schools": total_schools,
            "total_jobs": total_jobs
        }
    except Exception as e:
        logger.error(f"Failed to fetch admin stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch statistics"
        )


@router.get("/teachers/{teacher_id}")
async def get_teacher_details_admin(
    teacher_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Get detailed teacher profile for admin view
    Includes all profile data and file URLs
    """
    supabase = get_supabase_client()

    response = supabase.table("teachers").select("*").eq("id", teacher_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )

    teacher = response.data

    # Add file URLs if available
    try:
        if teacher.get("cv_path"):
            teacher["cv_url"] = StorageService.get_teacher_cv_url(
                teacher["id"],
                teacher["cv_path"]
            )
    except Exception as e:
        logger.error(f"Error getting CV URL: {e}")
        teacher["cv_url"] = None

    try:
        if teacher.get("headshot_photo_path"):
            teacher["headshot_url"] = StorageService.get_teacher_headshot_url(
                teacher["id"],
                teacher["headshot_photo_path"]
            )
    except Exception as e:
        logger.error(f"Error getting headshot URL: {e}")
        teacher["headshot_url"] = None

    try:
        if teacher.get("intro_video_path"):
            teacher["video_url"] = StorageService.get_teacher_video_url(
                teacher["id"],
                teacher["intro_video_path"]
            )
    except Exception as e:
        logger.error(f"Error getting video URL: {e}")
        teacher["video_url"] = None

    return teacher


@router.get("/teachers/{teacher_id}/cv-url")
async def get_teacher_cv_url(
    teacher_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Get signed URL for teacher's CV (Admin only)
    """
    supabase = get_supabase_client()

    response = supabase.table("teachers").select("cv_path").eq("id", teacher_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )

    if not response.data.get("cv_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not uploaded"
        )

    try:
        signed_url = StorageService.get_teacher_cv_url(
            teacher_id,
            response.data["cv_path"]
        )
        return {"cv_url": signed_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get CV URL: {str(e)}"
        )


@router.get("/teachers/{teacher_id}/cv-download")
async def download_teacher_cv(
    teacher_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Redirect to signed URL for teacher's CV download (Admin only)
    """
    from fastapi.responses import RedirectResponse

    supabase = get_supabase_client()

    response = supabase.table("teachers").select("cv_path").eq("id", teacher_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )

    if not response.data.get("cv_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not uploaded"
        )

    try:
        signed_url = StorageService.get_teacher_cv_url(
            teacher_id,
            response.data["cv_path"]
        )
        return RedirectResponse(url=signed_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get CV: {str(e)}"
        )

from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.dependencies import get_current_admin
from app.db.supabase import get_supabase_client
from app.services.storage_service import StorageService
from typing import Optional
from datetime import datetime, timedelta
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

        # Get total schools count (from schools table)
        schools_response = supabase.table("schools").select("id", count="exact").execute()
        total_schools = schools_response.count or 0

        # Get total jobs count (from jobs table)
        jobs_response = supabase.table("jobs").select("id", count="exact").execute()
        total_jobs = jobs_response.count or 0

        # Get total school_jobs count (jobs posted by school accounts)
        school_jobs_response = supabase.table("school_jobs").select("id", count="exact").execute()
        total_school_jobs = school_jobs_response.count or 0

        # Get total interview selections count
        selections_response = supabase.table("school_interview_selections").select("id", count="exact").execute()
        total_interview_selections = selections_response.count or 0

        # Get paid school accounts count
        paid_schools_response = supabase.table("school_accounts").select("id", count="exact").eq("has_paid", True).execute()
        paid_schools = paid_schools_response.count or 0

        return {
            "total_teachers": total_teachers,
            "paid_teachers": paid_teachers,
            "active_applications": active_applications,
            "placed_teachers": placed_teachers,
            "total_schools": total_schools,
            "total_jobs": total_jobs,
            "total_school_jobs": total_school_jobs,
            "total_interview_selections": total_interview_selections,
            "paid_schools": paid_schools,
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


# ============================================================================
# INTERVIEW SELECTIONS (ADMIN)
# ============================================================================

@router.get("/interview-selections")
async def get_admin_interview_selections(
    admin: dict = Depends(get_current_admin),
    status_filter: Optional[str] = None,
    school_account_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Get all interview selections across all schools (Admin only)
    """
    supabase = get_supabase_client()

    # Get total count first
    count_query = supabase.table("school_interview_selections").select("id", count="exact")
    if status_filter:
        count_query = count_query.eq("status", status_filter)
    if school_account_id:
        count_query = count_query.eq("school_account_id", school_account_id)
    count_response = count_query.execute()
    total = count_response.count or 0

    # Get selections with related data
    query = supabase.table("school_interview_selections").select(
        "*, teachers(*), school_jobs(*), school_accounts(*)"
    )

    if status_filter:
        query = query.eq("status", status_filter)
    if school_account_id:
        query = query.eq("school_account_id", school_account_id)

    response = query.order("selected_at", desc=True).range(offset, offset + limit - 1).execute()
    selections = response.data or []

    result = []
    for selection in selections:
        teacher = selection.get("teachers", {}) or {}
        job = selection.get("school_jobs", {}) or {}
        school = selection.get("school_accounts", {}) or {}

        # Generate headshot URL
        headshot_url = None
        if teacher.get("headshot_photo_path"):
            try:
                headshot_url = StorageService.get_teacher_headshot_url(
                    teacher["id"], teacher["headshot_photo_path"]
                )
            except Exception as e:
                logger.error(f"Error generating headshot URL: {e}")

        result.append({
            "id": selection["id"],
            "status": selection["status"],
            "notes": selection.get("notes"),
            "selected_at": selection["selected_at"],
            "status_updated_at": selection.get("status_updated_at") or selection["selected_at"],
            "teacher_id": selection["teacher_id"],
            "teacher_name": f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip() or None,
            "teacher_email": teacher.get("email"),
            "teacher_subject": teacher.get("subject_specialty"),
            "teacher_location": teacher.get("preferred_location"),
            "teacher_headshot_url": headshot_url,
            "school_job_id": selection.get("school_job_id"),
            "job_title": job.get("title"),
            "job_city": job.get("city"),
            "school_account_id": selection["school_account_id"],
            "school_name": school.get("school_name"),
            "school_city": school.get("city"),
            "school_email": school.get("contact_email"),
        })

    return {"selections": result, "total": total}


@router.get("/interview-selections/recent")
async def get_admin_recent_interview_selections(
    admin: dict = Depends(get_current_admin),
    hours: int = Query(default=24, ge=1, le=168)
):
    """
    Get recent interview selections from the last N hours (Admin only)
    """
    supabase = get_supabase_client()

    # Calculate the cutoff time
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()

    # Get selections with related data
    response = supabase.table("school_interview_selections").select(
        "*, teachers(*), school_jobs(*), school_accounts(*)"
    ).gte("selected_at", cutoff_str).order("selected_at", desc=True).execute()

    selections = response.data or []

    result = []
    for selection in selections:
        teacher = selection.get("teachers", {}) or {}
        job = selection.get("school_jobs", {}) or {}
        school = selection.get("school_accounts", {}) or {}

        # Generate headshot URL
        headshot_url = None
        if teacher.get("headshot_photo_path"):
            try:
                headshot_url = StorageService.get_teacher_headshot_url(
                    teacher["id"], teacher["headshot_photo_path"]
                )
            except Exception as e:
                logger.error(f"Error generating headshot URL: {e}")

        result.append({
            "id": selection["id"],
            "status": selection["status"],
            "notes": selection.get("notes"),
            "selected_at": selection["selected_at"],
            "status_updated_at": selection.get("status_updated_at") or selection["selected_at"],
            "teacher_id": selection["teacher_id"],
            "teacher_name": f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip() or None,
            "teacher_email": teacher.get("email"),
            "teacher_subject": teacher.get("subject_specialty"),
            "teacher_location": teacher.get("preferred_location"),
            "teacher_headshot_url": headshot_url,
            "school_job_id": selection.get("school_job_id"),
            "job_title": job.get("title"),
            "job_city": job.get("city"),
            "school_account_id": selection["school_account_id"],
            "school_name": school.get("school_name"),
            "school_city": school.get("city"),
            "school_email": school.get("contact_email"),
        })

    return {
        "selections": result,
        "count": len(result),
        "since_hours": hours
    }


@router.get("/interview-selections/stats")
async def get_admin_interview_selection_stats(
    admin: dict = Depends(get_current_admin)
):
    """
    Get interview selection statistics (Admin only)
    """
    supabase = get_supabase_client()

    # Get total count
    total_response = supabase.table("school_interview_selections").select(
        "id", count="exact"
    ).execute()

    # Get all selections for status breakdown
    selections_response = supabase.table("school_interview_selections").select(
        "status, school_account_id, selected_at"
    ).execute()

    selections = selections_response.data or []

    # Count by status
    by_status = {}
    unique_schools = set()
    last_7_days = 0
    cutoff_7d = datetime.utcnow() - timedelta(days=7)

    for selection in selections:
        s = selection.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        unique_schools.add(selection["school_account_id"])

        # Check if within last 7 days
        selected_at = selection.get("selected_at", "")
        if selected_at:
            try:
                selected_dt = datetime.fromisoformat(selected_at.replace("Z", "+00:00"))
                if selected_dt.replace(tzinfo=None) > cutoff_7d:
                    last_7_days += 1
            except (ValueError, AttributeError):
                pass

    return {
        "total_selections": total_response.count or 0,
        "by_status": by_status,
        "last_7_days": last_7_days,
        "unique_schools_selecting": len(unique_schools),
    }


# ============================================================================
# SCHOOL JOBS (ADMIN)
# ============================================================================

@router.get("/school-jobs")
async def get_admin_school_jobs(
    admin: dict = Depends(get_current_admin),
    is_active: Optional[bool] = None,
    school_account_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Get all school jobs across all schools (Admin only)
    """
    supabase = get_supabase_client()

    # Get total count
    count_query = supabase.table("school_jobs").select("id", count="exact")
    if is_active is not None:
        count_query = count_query.eq("is_active", is_active)
    if school_account_id:
        count_query = count_query.eq("school_account_id", school_account_id)
    count_response = count_query.execute()
    total = count_response.count or 0

    # Get jobs with school data
    query = supabase.table("school_jobs").select("*, school_accounts(*)")

    if is_active is not None:
        query = query.eq("is_active", is_active)
    if school_account_id:
        query = query.eq("school_account_id", school_account_id)

    response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    jobs = response.data or []

    result = []
    for job in jobs:
        school = job.get("school_accounts", {}) or {}

        # Get match count
        match_count_resp = supabase.table("school_job_matches").select(
            "id", count="exact"
        ).eq("school_job_id", job["id"]).execute()

        # Get selection count
        selection_count_resp = supabase.table("school_interview_selections").select(
            "id", count="exact"
        ).eq("school_job_id", job["id"]).execute()

        job_data = {
            **{k: v for k, v in job.items() if k != "school_accounts"},
            "school_name": school.get("school_name"),
            "school_city": school.get("city"),
            "match_count": match_count_resp.count or 0,
            "selection_count": selection_count_resp.count or 0,
        }
        result.append(job_data)

    return {"jobs": result, "total": total}

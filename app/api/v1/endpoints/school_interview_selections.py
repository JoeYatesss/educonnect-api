from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from app.models.school_job import (
    InterviewSelectionCreate, InterviewSelectionUpdate,
    InterviewSelectionResponse, InterviewSelectionWithDetails,
    InterviewSelectionStatus
)
from app.dependencies import require_school_payment
from app.db.supabase import get_supabase_client
from app.services.storage_service import StorageService
from app.middleware.rate_limit import limiter
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# INTERVIEW SELECTION CRUD ENDPOINTS
# ============================================================================

@router.get("/", response_model=List[InterviewSelectionWithDetails])
async def list_interview_selections(
    school: dict = Depends(require_school_payment),
    status_filter: Optional[InterviewSelectionStatus] = Query(default=None, alias="status"),
    school_job_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    List all interview selections for the current school.
    Includes teacher and job details.
    """
    supabase = get_supabase_client()

    # Build query with joins
    query = supabase.table("school_interview_selections").select(
        "*, teachers(*), school_jobs(id, title, city)"
    ).eq("school_account_id", school["id"])

    if status_filter is not None:
        query = query.eq("status", status_filter.value)

    if school_job_id is not None:
        query = query.eq("school_job_id", school_job_id)

    response = query.order("selected_at", desc=True).range(
        offset, offset + limit - 1
    ).execute()

    selections = response.data or []

    # Transform to include full details with signed URLs
    result = []
    for selection in selections:
        teacher = selection.get("teachers", {}) or {}
        job = selection.get("school_jobs", {}) or {}

        # Generate headshot URL
        headshot_url = None
        try:
            if teacher.get("headshot_photo_path"):
                headshot_url = StorageService.get_teacher_headshot_url(
                    teacher["id"], teacher["headshot_photo_path"]
                )
        except Exception as e:
            logger.error(f"Error generating headshot URL: {e}")

        result.append({
            "id": selection["id"],
            "school_account_id": selection["school_account_id"],
            "teacher_id": selection["teacher_id"],
            "school_job_id": selection.get("school_job_id"),
            "status": selection["status"],
            "notes": selection.get("notes"),
            "selected_at": selection["selected_at"],
            "status_updated_at": selection["status_updated_at"],
            "teacher": teacher,
            "school_job": job,
            "school_account": None,
            "teacher_name": f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip() if teacher else None,
            "teacher_email": teacher.get("email"),
            "teacher_headshot_url": headshot_url,
            "job_title": job.get("title"),
            "school_name": school.get("school_name"),
        })

    return result


@router.post("/", response_model=InterviewSelectionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/hour")
async def create_interview_selection(
    request: Request,
    selection_data: InterviewSelectionCreate,
    school: dict = Depends(require_school_payment)
):
    """
    Select a teacher for interview.
    Creates a new selection record with status 'selected_for_interview'.
    """
    supabase = get_supabase_client()

    # Verify teacher exists and has paid
    teacher = supabase.table("teachers").select("id, has_paid").eq(
        "id", selection_data.teacher_id
    ).single().execute()

    if not teacher.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )

    if not teacher.data.get("has_paid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot select unpaid teachers for interview"
        )

    # If job_id provided, verify it belongs to this school
    if selection_data.school_job_id:
        job = supabase.table("school_jobs").select("id").eq(
            "id", selection_data.school_job_id
        ).eq("school_account_id", school["id"]).single().execute()

        if not job.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )

    # Check if selection already exists
    existing = supabase.table("school_interview_selections").select("id").eq(
        "school_account_id", school["id"]
    ).eq("teacher_id", selection_data.teacher_id)

    if selection_data.school_job_id:
        existing = existing.eq("school_job_id", selection_data.school_job_id)
    else:
        existing = existing.is_("school_job_id", "null")

    existing_result = existing.execute()

    if existing_result.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Teacher already selected for this job"
        )

    # Create selection
    selection_dict = {
        "school_account_id": school["id"],
        "teacher_id": selection_data.teacher_id,
        "school_job_id": selection_data.school_job_id,
        "notes": selection_data.notes,
        "status": "selected_for_interview",
    }

    response = supabase.table("school_interview_selections").insert(selection_dict).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create selection"
        )

    logger.info(f"School {school['id']} selected teacher {selection_data.teacher_id} for interview")

    return response.data[0]


@router.get("/{selection_id}", response_model=InterviewSelectionWithDetails)
async def get_interview_selection(
    selection_id: int,
    school: dict = Depends(require_school_payment)
):
    """Get a specific interview selection with full details"""
    supabase = get_supabase_client()

    response = supabase.table("school_interview_selections").select(
        "*, teachers(*), school_jobs(id, title, city)"
    ).eq("id", selection_id).eq("school_account_id", school["id"]).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selection not found"
        )

    selection = response.data
    teacher = selection.get("teachers", {}) or {}
    job = selection.get("school_jobs", {}) or {}

    # Generate URLs
    headshot_url = None
    cv_url = None
    video_url = None

    try:
        if teacher.get("headshot_photo_path"):
            headshot_url = StorageService.get_teacher_headshot_url(
                teacher["id"], teacher["headshot_photo_path"]
            )
        if teacher.get("cv_path"):
            cv_url = StorageService.get_teacher_cv_url(
                teacher["id"], teacher["cv_path"]
            )
        if teacher.get("intro_video_path"):
            video_url = StorageService.get_teacher_video_url(
                teacher["id"], teacher["intro_video_path"]
            )
    except Exception as e:
        logger.error(f"Error generating URLs: {e}")

    # Add URLs to teacher data
    if teacher:
        teacher["headshot_url"] = headshot_url
        teacher["cv_url"] = cv_url
        teacher["video_url"] = video_url

    return {
        "id": selection["id"],
        "school_account_id": selection["school_account_id"],
        "teacher_id": selection["teacher_id"],
        "school_job_id": selection.get("school_job_id"),
        "status": selection["status"],
        "notes": selection.get("notes"),
        "selected_at": selection["selected_at"],
        "status_updated_at": selection["status_updated_at"],
        "teacher": teacher,
        "school_job": job,
        "school_account": None,
        "teacher_name": f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip() if teacher else None,
        "teacher_email": teacher.get("email"),
        "teacher_headshot_url": headshot_url,
        "job_title": job.get("title"),
        "school_name": school.get("school_name"),
    }


@router.patch("/{selection_id}", response_model=InterviewSelectionResponse)
async def update_interview_selection(
    selection_id: int,
    update_data: InterviewSelectionUpdate,
    school: dict = Depends(require_school_payment)
):
    """Update an interview selection (status or notes)"""
    supabase = get_supabase_client()

    # Verify selection belongs to school
    existing = supabase.table("school_interview_selections").select("id, status").eq(
        "id", selection_id
    ).eq("school_account_id", school["id"]).single().execute()

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selection not found"
        )

    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        return existing.data

    # Convert enum to string value if present
    if "status" in update_dict and update_dict["status"]:
        update_dict["status"] = update_dict["status"].value

    response = supabase.table("school_interview_selections").update(update_dict).eq(
        "id", selection_id
    ).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update selection"
        )

    logger.info(f"Selection {selection_id} updated: {update_dict}")

    return response.data[0]


@router.delete("/{selection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview_selection(
    selection_id: int,
    school: dict = Depends(require_school_payment)
):
    """Remove an interview selection"""
    supabase = get_supabase_client()

    # Verify selection belongs to school
    existing = supabase.table("school_interview_selections").select("id").eq(
        "id", selection_id
    ).eq("school_account_id", school["id"]).single().execute()

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selection not found"
        )

    supabase.table("school_interview_selections").delete().eq("id", selection_id).execute()

    logger.info(f"Selection {selection_id} deleted by school {school['id']}")

    return None


# ============================================================================
# BULK OPERATIONS
# ============================================================================

@router.post("/bulk-select", response_model=List[InterviewSelectionResponse])
@limiter.limit("10/hour")
async def bulk_select_teachers(
    request: Request,
    teacher_ids: List[int],
    school: dict = Depends(require_school_payment),
    school_job_id: Optional[int] = None,
    notes: Optional[str] = None
):
    """
    Select multiple teachers for interview at once.
    Returns list of created selections.
    """
    supabase = get_supabase_client()

    if not teacher_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No teacher IDs provided"
        )

    if len(teacher_ids) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 20 teachers can be selected at once"
        )

    # Verify all teachers exist and have paid
    teachers = supabase.table("teachers").select("id, has_paid").in_(
        "id", teacher_ids
    ).execute()

    if not teachers.data or len(teachers.data) != len(teacher_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Some teachers not found"
        )

    unpaid = [t["id"] for t in teachers.data if not t.get("has_paid")]
    if unpaid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot select unpaid teachers: {unpaid}"
        )

    # If job_id provided, verify it
    if school_job_id:
        job = supabase.table("school_jobs").select("id").eq(
            "id", school_job_id
        ).eq("school_account_id", school["id"]).single().execute()

        if not job.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )

    # Get existing selections to avoid duplicates
    existing_query = supabase.table("school_interview_selections").select(
        "teacher_id"
    ).eq("school_account_id", school["id"]).in_("teacher_id", teacher_ids)

    if school_job_id:
        existing_query = existing_query.eq("school_job_id", school_job_id)
    else:
        existing_query = existing_query.is_("school_job_id", "null")

    existing = existing_query.execute()
    existing_teacher_ids = {e["teacher_id"] for e in (existing.data or [])}

    # Create selections for new teachers
    new_teacher_ids = [t for t in teacher_ids if t not in existing_teacher_ids]

    if not new_teacher_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="All teachers already selected"
        )

    selections_to_create = [
        {
            "school_account_id": school["id"],
            "teacher_id": teacher_id,
            "school_job_id": school_job_id,
            "notes": notes,
            "status": "selected_for_interview",
        }
        for teacher_id in new_teacher_ids
    ]

    response = supabase.table("school_interview_selections").insert(selections_to_create).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create selections"
        )

    logger.info(f"School {school['id']} bulk selected {len(new_teacher_ids)} teachers")

    return response.data


# ============================================================================
# STATS
# ============================================================================

@router.get("/stats/summary")
async def get_selection_stats(
    school: dict = Depends(require_school_payment)
):
    """Get interview selection statistics for the school"""
    supabase = get_supabase_client()

    # Get total selections
    total = supabase.table("school_interview_selections").select(
        "id", count="exact"
    ).eq("school_account_id", school["id"]).execute()

    # Get counts by status
    selections = supabase.table("school_interview_selections").select(
        "status"
    ).eq("school_account_id", school["id"]).execute()

    status_counts = {}
    for selection in selections.data or []:
        s = selection.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "total_selections": total.count or 0,
        "by_status": status_counts,
    }

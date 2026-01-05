from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from app.models.school import SchoolCreate, SchoolUpdate, SchoolResponse
from app.dependencies import get_current_admin
from app.db.supabase import get_supabase_client
from app.services.matching_service import MatchingService
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# Fields that affect matching - if updated, re-run matching algorithm
MATCHING_FIELDS = {'subjects_needed', 'age_groups', 'city', 'province', 'experience_required', 'chinese_required'}


router = APIRouter()


@router.post("/", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
async def create_school(
    school: SchoolCreate,
    admin: dict = Depends(get_current_admin),
    background_tasks: BackgroundTasks = None
):
    """
    Create a new school (Admin only).
    Automatically triggers matching against all teachers in background.
    """
    supabase = get_supabase_client()

    school_data = school.model_dump()
    response = supabase.table("schools").insert(school_data).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create school"
        )

    created_school = response.data[0]

    # Trigger matching in background for the new school
    if background_tasks:
        logger.info(f"New school {created_school['id']} created, triggering matching")
        background_tasks.add_task(
            _run_matching_for_school,
            created_school["id"]
        )

    return created_school


@router.get("/", response_model=List[SchoolResponse])
async def list_schools(
    admin: dict = Depends(get_current_admin),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    is_active: Optional[bool] = None
):
    """
    List all schools (Admin only)
    """
    supabase = get_supabase_client()

    query = supabase.table("schools").select("*")

    if is_active is not None:
        query = query.eq("is_active", is_active)

    response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    return response.data or []


@router.get("/{school_id}", response_model=SchoolResponse)
async def get_school(
    school_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Get school by ID (Admin only)
    """
    supabase = get_supabase_client()

    response = supabase.table("schools").select("*").eq("id", school_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )

    return response.data


@router.patch("/{school_id}", response_model=SchoolResponse)
async def update_school(
    school_id: int,
    school_update: SchoolUpdate,
    admin: dict = Depends(get_current_admin),
    background_tasks: BackgroundTasks = None
):
    """
    Update school (Admin only).
    Automatically re-runs matching if matching-relevant fields are updated.
    """
    supabase = get_supabase_client()

    update_dict = school_update.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    response = supabase.table("schools").update(update_dict).eq("id", school_id).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )

    # Check if any matching-relevant fields were updated
    updated_matching_fields = set(update_dict.keys()) & MATCHING_FIELDS
    if updated_matching_fields and background_tasks:
        logger.info(f"School {school_id} updated matching fields: {updated_matching_fields}, triggering re-match")
        background_tasks.add_task(
            _run_matching_for_school,
            school_id
        )

    return response.data[0]


def _run_matching_for_school(school_id: int):
    """Background task wrapper for school matching"""
    try:
        match_count = MatchingService.run_matching_for_school(school_id)
        logger.info(f"Auto-matching completed for school {school_id}: {match_count} matches found")
    except Exception as e:
        logger.error(f"Auto-matching failed for school {school_id}: {str(e)}")


@router.delete("/{school_id}")
async def delete_school(
    school_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Delete school (Admin only)
    """
    supabase = get_supabase_client()

    response = supabase.table("schools").delete().eq("id", school_id).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )

    return {"message": "School deleted successfully"}

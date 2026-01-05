from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from app.models.job import JobCreate, JobUpdate, JobResponse
from app.dependencies import get_current_admin
from app.db.supabase import get_supabase_client
from app.middleware.rate_limit import limiter
from typing import List, Optional


router = APIRouter()


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/hour")
async def create_job(
    request: Request,
    job: JobCreate,
    admin: dict = Depends(get_current_admin)
):
    """
    Create a new job posting (Admin only)

    Creates a job posting with all required and optional fields.
    """
    supabase = get_supabase_client()

    job_data = job.model_dump()
    response = supabase.table("jobs").insert(job_data).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job"
        )

    return response.data[0]


@router.get("/", response_model=List[JobResponse])
async def list_jobs(
    admin: dict = Depends(get_current_admin),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    is_active: Optional[bool] = None,
    city: Optional[str] = None
):
    """
    List all jobs (Admin only)

    - **limit**: Maximum number of jobs to return (1-100, default 50)
    - **offset**: Number of jobs to skip for pagination (default 0)
    - **is_active**: Filter by active status (true/false, optional)
    - **city**: Filter by city (optional)
    """
    supabase = get_supabase_client()

    query = supabase.table("jobs").select("*")

    if is_active is not None:
        query = query.eq("is_active", is_active)

    if city:
        query = query.eq("city", city)

    response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    return response.data or []


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Get job by ID (Admin only)

    Returns full job details including all fields.
    """
    supabase = get_supabase_client()

    response = supabase.table("jobs").select("*").eq("id", job_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    return response.data


@router.patch("/{job_id}", response_model=JobResponse)
@limiter.limit("60/hour")
async def update_job(
    request: Request,
    job_id: int,
    job_update: JobUpdate,
    admin: dict = Depends(get_current_admin)
):
    """
    Update job (Admin only)

    Only updates fields that are provided (partial update).
    """
    supabase = get_supabase_client()

    update_dict = job_update.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    response = supabase.table("jobs").update(update_dict).eq("id", job_id).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    return response.data[0]


@router.delete("/{job_id}")
@limiter.limit("20/hour")
async def delete_job(
    request: Request,
    job_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Delete job (Admin only)

    Permanently removes the job posting from the database.
    """
    supabase = get_supabase_client()

    response = supabase.table("jobs").delete().eq("id", job_id).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    return {"message": "Job deleted successfully"}

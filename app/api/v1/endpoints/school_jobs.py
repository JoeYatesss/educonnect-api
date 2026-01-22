from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from app.models.school_job import (
    SchoolJobCreate, SchoolJobUpdate, SchoolJobResponse, SchoolJobWithStats,
    SchoolJobMatchResponse, RunMatchingResponse
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
# HELPER FUNCTIONS
# ============================================================================

def get_school_active_job_count(supabase, school_account_id: int) -> int:
    """Get count of active jobs for a school"""
    result = supabase.table("school_jobs").select(
        "id", count="exact"
    ).eq("school_account_id", school_account_id).eq("is_active", True).execute()
    return result.count or 0


def get_school_max_jobs(supabase, school_account_id: int) -> int:
    """Get max active jobs allowed for a school"""
    result = supabase.table("school_accounts").select(
        "max_active_jobs"
    ).eq("id", school_account_id).single().execute()
    return result.data.get("max_active_jobs", 5) if result.data else 5


# ============================================================================
# SCHOOL JOB CRUD ENDPOINTS
# ============================================================================

@router.get("/", response_model=List[SchoolJobWithStats])
async def list_school_jobs(
    school: dict = Depends(require_school_payment),
    is_active: Optional[bool] = None,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0)
):
    """
    List all jobs for the current school.
    Includes match and selection counts for each job.
    """
    supabase = get_supabase_client()

    # Build query
    query = supabase.table("school_jobs").select("*").eq(
        "school_account_id", school["id"]
    )

    if is_active is not None:
        query = query.eq("is_active", is_active)

    response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    jobs = response.data or []

    # Get match and selection counts for each job
    result = []
    for job in jobs:
        # Get match count
        match_count_resp = supabase.table("school_job_matches").select(
            "id", count="exact"
        ).eq("school_job_id", job["id"]).execute()

        # Get selection count
        selection_count_resp = supabase.table("school_interview_selections").select(
            "id", count="exact"
        ).eq("school_job_id", job["id"]).execute()

        job_with_stats = {
            **job,
            "match_count": match_count_resp.count or 0,
            "selection_count": selection_count_resp.count or 0
        }
        result.append(job_with_stats)

    return result


@router.post("/", response_model=SchoolJobResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/hour")
async def create_school_job(
    request: Request,
    job_data: SchoolJobCreate,
    school: dict = Depends(require_school_payment)
):
    """
    Create a new job posting for the current school.
    Enforces maximum active jobs limit.
    """
    supabase = get_supabase_client()

    # Check if school has reached max active jobs
    if job_data.is_active:
        active_count = get_school_active_job_count(supabase, school["id"])
        max_jobs = get_school_max_jobs(supabase, school["id"])

        if active_count >= max_jobs:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Maximum active jobs limit reached ({max_jobs}). Please deactivate an existing job first."
            )

    # Create job
    job_dict = job_data.model_dump()
    job_dict["school_account_id"] = school["id"]

    response = supabase.table("school_jobs").insert(job_dict).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job posting"
        )

    return response.data[0]


@router.get("/{job_id}", response_model=SchoolJobWithStats)
async def get_school_job(
    job_id: int,
    school: dict = Depends(require_school_payment)
):
    """Get a specific job posting with stats"""
    supabase = get_supabase_client()

    response = supabase.table("school_jobs").select("*").eq(
        "id", job_id
    ).eq("school_account_id", school["id"]).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    job = response.data

    # Get match count
    match_count_resp = supabase.table("school_job_matches").select(
        "id", count="exact"
    ).eq("school_job_id", job_id).execute()

    # Get selection count
    selection_count_resp = supabase.table("school_interview_selections").select(
        "id", count="exact"
    ).eq("school_job_id", job_id).execute()

    return {
        **job,
        "match_count": match_count_resp.count or 0,
        "selection_count": selection_count_resp.count or 0
    }


@router.patch("/{job_id}", response_model=SchoolJobResponse)
async def update_school_job(
    job_id: int,
    update_data: SchoolJobUpdate,
    school: dict = Depends(require_school_payment)
):
    """Update a job posting"""
    supabase = get_supabase_client()

    # Verify job belongs to school
    existing = supabase.table("school_jobs").select("id, is_active").eq(
        "id", job_id
    ).eq("school_account_id", school["id"]).single().execute()

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    update_dict = update_data.model_dump(exclude_unset=True)

    # Check max jobs limit if activating a job
    if update_dict.get("is_active") and not existing.data.get("is_active"):
        active_count = get_school_active_job_count(supabase, school["id"])
        max_jobs = get_school_max_jobs(supabase, school["id"])

        if active_count >= max_jobs:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Maximum active jobs limit reached ({max_jobs}). Please deactivate an existing job first."
            )

    if not update_dict:
        return existing.data

    response = supabase.table("school_jobs").update(update_dict).eq("id", job_id).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update job posting"
        )

    return response.data[0]


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_school_job(
    job_id: int,
    school: dict = Depends(require_school_payment)
):
    """Delete a job posting"""
    supabase = get_supabase_client()

    # Verify job belongs to school
    existing = supabase.table("school_jobs").select("id").eq(
        "id", job_id
    ).eq("school_account_id", school["id"]).single().execute()

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    # Delete job (cascades to matches and selections)
    supabase.table("school_jobs").delete().eq("id", job_id).execute()

    return None


# ============================================================================
# JOB MATCHING ENDPOINTS
# ============================================================================

@router.post("/{job_id}/run-matching", response_model=RunMatchingResponse)
@limiter.limit("10/hour")
async def run_job_matching(
    request: Request,
    job_id: int,
    school: dict = Depends(require_school_payment),
    min_score: float = Query(default=50.0, ge=0, le=100)
):
    """
    Run matching algorithm for a job against all paid teachers.
    Returns the number of matches created.
    """
    supabase = get_supabase_client()

    # Verify job belongs to school and is active
    job_response = supabase.table("school_jobs").select("*").eq(
        "id", job_id
    ).eq("school_account_id", school["id"]).single().execute()

    if not job_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    job = job_response.data

    if not job.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot run matching on inactive job"
        )

    # Import matching service here to avoid circular imports
    from app.services.matching_service import MatchingService, parse_comma_separated, parse_years_experience

    # Get all paid teachers
    teachers_response = supabase.table("teachers").select("*").eq("has_paid", True).execute()
    teachers = teachers_response.data or []

    logger.info(f"Running matching for school job {job_id} against {len(teachers)} paid teachers")

    match_count = 0
    for teacher in teachers:
        # Calculate match score using the job's criteria
        score, reasons = calculate_school_job_match_score(teacher, job)

        if score >= min_score:
            match_data = {
                "school_job_id": job_id,
                "teacher_id": teacher["id"],
                "school_account_id": school["id"],
                "match_score": score,
                "match_reasons": reasons,
            }

            # Upsert match (update if exists, insert if not)
            supabase.table("school_job_matches").upsert(
                match_data,
                on_conflict="school_job_id,teacher_id"
            ).execute()
            match_count += 1
        else:
            # Remove match if score dropped below threshold
            supabase.table("school_job_matches").delete().eq(
                "teacher_id", teacher["id"]
            ).eq("school_job_id", job_id).execute()

    logger.info(f"Created {match_count} matches for school job {job_id}")

    return RunMatchingResponse(
        job_id=job_id,
        matches_created=match_count,
        message=f"Successfully matched {match_count} teachers to this job"
    )


@router.get("/{job_id}/matches", response_model=List[SchoolJobMatchResponse])
async def get_job_matches(
    job_id: int,
    school: dict = Depends(require_school_payment),
    min_score: Optional[float] = Query(default=None, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Get matched teachers for a job.
    Returns full teacher details with match scores.
    """
    supabase = get_supabase_client()

    # Verify job belongs to school
    job = supabase.table("school_jobs").select("id").eq(
        "id", job_id
    ).eq("school_account_id", school["id"]).single().execute()

    if not job.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    # Build query for matches with teacher data
    query = supabase.table("school_job_matches").select(
        "*, teachers(*)"
    ).eq("school_job_id", job_id)

    if min_score is not None:
        query = query.gte("match_score", min_score)

    response = query.order("match_score", desc=True).range(
        offset, offset + limit - 1
    ).execute()

    matches = response.data or []

    # Check if teacher is already selected for interview
    selections_response = supabase.table("school_interview_selections").select(
        "teacher_id"
    ).eq("school_job_id", job_id).eq("school_account_id", school["id"]).execute()
    selected_teacher_ids = {s["teacher_id"] for s in (selections_response.data or [])}

    # Transform matches to include full teacher details with signed URLs
    result = []
    for match in matches:
        teacher = match.get("teachers", {}) or {}

        teacher_data = {
            "id": teacher.get("id"),
            "first_name": teacher.get("first_name"),
            "last_name": teacher.get("last_name"),
            "email": teacher.get("email"),
            "phone": teacher.get("phone"),
            "nationality": teacher.get("nationality"),
            "preferred_location": teacher.get("preferred_location"),
            "subject_specialty": teacher.get("subject_specialty"),
            "preferred_age_group": teacher.get("preferred_age_group"),
            "years_experience": teacher.get("years_experience"),
            "education": teacher.get("education"),
            "teaching_experience": teacher.get("teaching_experience"),
            "professional_experience": teacher.get("professional_experience"),
            "linkedin": teacher.get("linkedin"),
            "wechat_id": teacher.get("wechat_id"),
            "headshot_url": None,
            "cv_url": None,
            "video_url": None,
            "has_paid": teacher.get("has_paid", False),
            "is_selected_for_interview": teacher.get("id") in selected_teacher_ids,
        }

        # Generate signed URLs for files
        try:
            if teacher.get("headshot_photo_path"):
                teacher_data["headshot_url"] = StorageService.get_teacher_headshot_url(
                    teacher["id"], teacher["headshot_photo_path"]
                )
            if teacher.get("cv_path"):
                teacher_data["cv_url"] = StorageService.get_teacher_cv_url(
                    teacher["id"], teacher["cv_path"]
                )
            if teacher.get("intro_video_path"):
                teacher_data["video_url"] = StorageService.get_teacher_video_url(
                    teacher["id"], teacher["intro_video_path"]
                )
        except Exception as e:
            logger.error(f"Error generating URLs for teacher {teacher.get('id')}: {e}")

        result.append({
            "id": match["id"],
            "school_job_id": match["school_job_id"],
            "teacher_id": match["teacher_id"],
            "school_account_id": match["school_account_id"],
            "match_score": match["match_score"],
            "match_reasons": match.get("match_reasons", []),
            "matched_at": match["matched_at"],
            "teacher": teacher_data,
        })

    return result


# ============================================================================
# STATS ENDPOINT
# ============================================================================

@router.get("/stats/summary")
async def get_job_stats(
    school: dict = Depends(require_school_payment)
):
    """Get job statistics for the school"""
    supabase = get_supabase_client()

    # Get active jobs count
    active_jobs = supabase.table("school_jobs").select(
        "id", count="exact"
    ).eq("school_account_id", school["id"]).eq("is_active", True).execute()

    # Get total jobs count
    total_jobs = supabase.table("school_jobs").select(
        "id", count="exact"
    ).eq("school_account_id", school["id"]).execute()

    # Get max jobs allowed
    max_jobs = get_school_max_jobs(supabase, school["id"])

    # Get total matches count
    total_matches = supabase.table("school_job_matches").select(
        "id", count="exact"
    ).eq("school_account_id", school["id"]).execute()

    # Get total selections count
    total_selections = supabase.table("school_interview_selections").select(
        "id", count="exact"
    ).eq("school_account_id", school["id"]).execute()

    # Get selections by status
    selections_response = supabase.table("school_interview_selections").select(
        "status"
    ).eq("school_account_id", school["id"]).execute()

    status_counts = {}
    for selection in selections_response.data or []:
        s = selection.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "active_jobs": active_jobs.count or 0,
        "total_jobs": total_jobs.count or 0,
        "max_jobs": max_jobs,
        "total_matches": total_matches.count or 0,
        "total_selections": total_selections.count or 0,
        "selections_by_status": status_counts,
    }


# ============================================================================
# MATCHING ALGORITHM HELPER
# ============================================================================

def calculate_school_job_match_score(teacher: dict, job: dict) -> tuple[float, list]:
    """
    Calculate match score for teacher-school_job pair.
    Uses same weights as the main matching service.
    """
    from app.services.matching_service import (
        MatchingService,
        parse_comma_separated,
        parse_years_experience
    )

    # Extract teacher data
    teacher_locations = parse_comma_separated(teacher.get('preferred_location'))
    teacher_subjects = parse_comma_separated(teacher.get('subject_specialty'))
    teacher_age_groups = parse_comma_separated(teacher.get('preferred_age_group'))
    teacher_years = parse_years_experience(teacher.get('years_experience'))
    teacher_has_chinese = teacher.get('has_chinese', False)

    # Extract job data
    job_city = job.get('city', '') or ''
    job_province = job.get('province', '') or ''
    job_subjects = job.get('subjects', []) or []
    job_age_groups = job.get('age_groups', []) or []
    job_experience_req = job.get('experience_required', '') or ''
    job_chinese_req = job.get('chinese_required', False)

    # Calculate component scores
    location_score = MatchingService.calculate_location_score(
        teacher_locations, job_city, job_province
    )
    subject_score = MatchingService.calculate_subject_score(
        teacher_subjects, job_subjects
    )
    age_group_score = MatchingService.calculate_age_group_score(
        teacher_age_groups, job_age_groups
    )
    experience_score = MatchingService.calculate_experience_score(
        teacher_years, job_experience_req
    )
    chinese_score = MatchingService.calculate_chinese_score(
        teacher_has_chinese, job_chinese_req
    )

    # Calculate weighted total
    total_score = (
        location_score * MatchingService.WEIGHT_LOCATION +
        subject_score * MatchingService.WEIGHT_SUBJECT +
        age_group_score * MatchingService.WEIGHT_AGE_GROUP +
        experience_score * MatchingService.WEIGHT_EXPERIENCE +
        chinese_score * MatchingService.WEIGHT_CHINESE
    )

    # Generate match reasons
    reasons = []
    if location_score >= 70:
        city_display = job_city or job_province or 'China'
        reasons.append(f"Location match: {city_display}")
    if subject_score >= 70 and teacher_subjects and job_subjects:
        matching_subjects = set([s.lower() for s in teacher_subjects]) & set([s.lower() for s in job_subjects])
        if matching_subjects:
            reasons.append(f"Subject match: {', '.join(matching_subjects)}")
    if age_group_score >= 70 and teacher_age_groups and job_age_groups:
        matching_ages = set([a.lower() for a in teacher_age_groups]) & set([a.lower() for a in job_age_groups])
        if matching_ages:
            reasons.append(f"Age group match: {', '.join(matching_ages)}")
    if experience_score >= 80:
        reasons.append(f"Experience level ({teacher_years} years) matches requirements")
    if chinese_score == 100 and job_chinese_req:
        reasons.append("Chinese language proficiency")

    return round(total_score, 2), reasons

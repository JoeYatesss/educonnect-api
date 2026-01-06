from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.dependencies import get_current_teacher, get_current_admin, require_payment
from app.services.matching_service import MatchingService
from app.models.school import MatchResponse


class MatchUpdate(BaseModel):
    role_name: Optional[str] = None


class UnifiedMatchResponse(BaseModel):
    """Response model for unified school/job matches"""
    id: int
    type: str  # 'school' or 'job'
    city: Optional[str] = None
    province: Optional[str] = None
    school_type: Optional[str] = None
    age_groups: Optional[List[str]] = None
    salary_range: Optional[str] = None
    match_score: float
    match_reasons: Optional[List[str]] = None
    is_submitted: bool = False
    role_name: Optional[str] = None
    # IDs
    school_id: Optional[int] = None
    job_id: Optional[int] = None
    # Job-specific fields
    title: Optional[str] = None
    company: Optional[str] = None
    application_deadline: Optional[datetime] = None
    start_date: Optional[str] = None
    visa_sponsorship: Optional[bool] = None
    accommodation_provided: Optional[str] = None
    external_url: Optional[str] = None
    source: Optional[str] = None


router = APIRouter()


@router.post("/run")
async def run_matching(
    teacher_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Run matching algorithm for a specific teacher (Admin only)
    Calculates match scores and saves to database
    """
    try:
        matches = MatchingService.run_matching_for_teacher(teacher_id)
        return {
            "message": f"Matching complete. Found {len(matches)} matches.",
            "matches_count": len(matches)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Matching failed: {str(e)}"
        )


@router.get("/preview")
async def get_preview_matches(
    teacher: dict = Depends(get_current_teacher)
):
    """
    Get preview matches for unpaid users (limited to 3, anonymized)
    Get full matches for paid users
    Returns both school and job matches (unified format)
    """
    if teacher.get("has_paid"):
        # Return full matches for paid users (both school and job matches)
        matches = MatchingService.get_teacher_all_matches(teacher["id"])
        return matches

    # Return preview matches (first 3 with limited data) for unpaid users
    matches = MatchingService.get_teacher_all_matches(teacher["id"])

    # Limit to 3 preview matches
    preview = matches[:3] if matches else []

    return preview


@router.get("/me", response_model=List[UnifiedMatchResponse])
async def get_my_matches(
    teacher: dict = Depends(require_payment)
):
    """
    Get all matches for current teacher (both school and job matches)
    Requires payment to access
    Returns matches WITHOUT school names (anonymized)
    Includes TES job matches with deadline, start_date, visa info, etc.
    """
    matches = MatchingService.get_teacher_all_matches(teacher["id"])
    return matches


@router.get("/teacher/{teacher_id}")
async def get_teacher_matches_admin(
    teacher_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Get matches for a specific teacher (Admin only)
    Returns full match data including school IDs and job data
    """
    try:
        # For admin, we want full data including school IDs and job details
        from app.db.supabase import get_supabase_client
        supabase = get_supabase_client()

        response = supabase.table("teacher_school_matches").select(
            "*, schools(*), jobs(*)"
        ).eq("teacher_id", teacher_id).order("match_score", desc=True).execute()

        return response.data or []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get matches: {str(e)}"
        )


@router.get("/school/{school_id}")
async def get_school_matched_teachers(
    school_id: int,
    admin: dict = Depends(get_current_admin),
    limit: int = 50
):
    """
    Get matched teachers for a school (Admin only).
    Returns list of teachers with match scores and details.
    """
    try:
        matches = MatchingService.get_school_matches(school_id, limit)
        return matches
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get school matches: {str(e)}"
        )


@router.patch("/{match_id}")
async def update_match(
    match_id: int,
    update_data: MatchUpdate,
    admin: dict = Depends(get_current_admin)
):
    """
    Update a match (Admin only).
    Currently supports updating role_name.
    """
    try:
        from app.db.supabase import get_supabase_client
        supabase = get_supabase_client()

        update_dict = update_data.model_dump(exclude_unset=True)
        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        response = supabase.table("teacher_school_matches").update(
            update_dict
        ).eq("id", match_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Match not found"
            )

        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update match: {str(e)}"
        )

from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies import get_current_teacher, get_current_admin, require_payment
from app.services.matching_service import MatchingService
from app.models.school import MatchResponse
from typing import List


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
    """
    if teacher.get("has_paid"):
        # Return full matches for paid users
        matches = MatchingService.get_teacher_matches(teacher["id"])
        return matches

    # Return preview matches (first 3 with limited data) for unpaid users
    matches = MatchingService.get_teacher_matches(teacher["id"])

    # Limit to 3 preview matches
    preview = matches[:3] if matches else []

    return preview


@router.get("/me", response_model=List[MatchResponse])
async def get_my_matches(
    teacher: dict = Depends(require_payment)
):
    """
    Get anonymous matches for current teacher
    Requires payment to access
    Returns matches WITHOUT school names
    """
    matches = MatchingService.get_teacher_matches(teacher["id"])
    return matches


@router.get("/teacher/{teacher_id}")
async def get_teacher_matches_admin(
    teacher_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Get matches for a specific teacher (Admin only)
    Returns full match data including school IDs
    """
    try:
        # For admin, we want full data including school IDs
        from app.db.supabase import get_supabase_client
        supabase = get_supabase_client()

        response = supabase.table("teacher_school_matches").select(
            "*, schools(*)"
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

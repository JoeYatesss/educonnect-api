from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from app.models.school_account import (
    SchoolAccountUpdate, SchoolAccountResponse,
    TeacherPreviewResponse, TeacherFullResponse,
    SavedTeacherResponse
)
from app.dependencies import get_current_school_account, require_school_payment
from app.db.supabase import get_supabase_client
from app.services.storage_service import StorageService
from app.middleware.rate_limit import limiter
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/me", response_model=SchoolAccountResponse)
async def get_current_school_profile(
    school: dict = Depends(get_current_school_account)
):
    """Get current school's profile"""
    return school


@router.patch("/me", response_model=SchoolAccountResponse)
async def update_school_profile(
    update_data: SchoolAccountUpdate,
    school: dict = Depends(get_current_school_account)
):
    """Update current school's profile"""
    supabase = get_supabase_client()

    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        return school

    response = supabase.table("school_accounts").update(update_dict).eq("id", school["id"]).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update school profile"
        )

    return response.data[0]


@router.get("/teachers")
@limiter.limit("100/hour")
async def browse_teachers(
    request: Request,
    school: dict = Depends(get_current_school_account),
    search: Optional[str] = None,
    subject: Optional[str] = None,
    location: Optional[str] = None,
    age_group: Optional[str] = None,
    min_experience: Optional[int] = None,
    limit: int = Query(default=20, ge=1, le=50),
    skip: int = Query(default=0, ge=0)
):
    """
    Browse/search teachers
    Returns limited data for unpaid schools, full data for paid schools
    """
    logger.info(f"Browse teachers - filters: search={search}, subject={subject}, location={location}, age_group={age_group}")
    supabase = get_supabase_client()

    # Get total count first
    count_query = supabase.table("teachers").select("id", count="exact")

    # Apply search filter (OR across multiple fields)
    # Note: In PostgREST .or_() filter strings, use % as wildcard
    if search:
        count_query = count_query.or_(f"first_name.ilike.%{search}%,last_name.ilike.%{search}%,subject_specialty.ilike.%{search}%")

    # Apply dropdown filters using .ilike() method
    # IMPORTANT: PostgREST uses * as wildcard in URL params (converted to % in SQL)
    if subject:
        count_query = count_query.ilike("subject_specialty", f"*{subject}*")
        logger.info(f"Applied subject filter: *{subject}*")
    if location:
        count_query = count_query.ilike("preferred_location", f"*{location}*")
        logger.info(f"Applied location filter: *{location}*")
    if age_group:
        count_query = count_query.ilike("preferred_age_group", f"*{age_group}*")
        logger.info(f"Applied age_group filter: *{age_group}*")

    count_response = count_query.execute()
    total = count_response.count or 0
    logger.info(f"Browse teachers - count query returned {total} results")

    # Base query - show all registered teachers
    query = supabase.table("teachers").select("*")

    # Apply search filter (OR across multiple fields)
    if search:
        query = query.or_(f"first_name.ilike.%{search}%,last_name.ilike.%{search}%,subject_specialty.ilike.%{search}%")

    # Apply dropdown filters using .ilike() method with * wildcards
    if subject:
        query = query.ilike("subject_specialty", f"*{subject}*")
    if location:
        query = query.ilike("preferred_location", f"*{location}*")
    if age_group:
        query = query.ilike("preferred_age_group", f"*{age_group}*")
    if min_experience:
        # years_experience is stored as VARCHAR, need to handle this carefully
        pass  # Skip for now, can add later with proper type conversion

    response = query.order("created_at", desc=True).range(skip, skip + limit - 1).execute()
    teachers = response.data or []

    has_full_access = school.get("has_paid", False)

    # Return different data based on payment status
    if has_full_access:
        # Full teacher data with signed URLs
        result = []
        for teacher in teachers:
            teacher_data = {
                "id": teacher["id"],
                "first_name": teacher["first_name"],
                "last_name": teacher["last_name"],
                "email": teacher["email"],
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
                "created_at": teacher.get("created_at"),
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
                logger.error(f"Error generating URLs for teacher {teacher['id']}: {e}")

            result.append(teacher_data)

        return {
            "teachers": result,
            "total": total,
            "has_full_access": True
        }
    else:
        # Preview data only (anonymized)
        preview_teachers = [
            {
                "id": t["id"],
                "preferred_location": t.get("preferred_location"),
                "subject_specialty": t.get("subject_specialty"),
                "preferred_age_group": t.get("preferred_age_group"),
                "years_experience": t.get("years_experience"),
                "has_headshot": bool(t.get("headshot_photo_path")),
                "has_cv": bool(t.get("cv_path")),
                "has_video": bool(t.get("intro_video_path")),
            }
            for t in teachers
        ]
        return {
            "teachers": preview_teachers,
            "total": total,
            "has_full_access": False
        }


@router.get("/teachers/{teacher_id}")
async def get_teacher_detail(
    teacher_id: int,
    school: dict = Depends(require_school_payment)
):
    """
    Get full teacher profile (paid schools only)
    """
    supabase = get_supabase_client()

    response = supabase.table("teachers").select("*").eq("id", teacher_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )

    teacher = response.data

    # Build full teacher response with signed URLs
    result = {
        "id": teacher["id"],
        "first_name": teacher["first_name"],
        "last_name": teacher["last_name"],
        "email": teacher["email"],
        "phone": teacher.get("phone"),
        "nationality": teacher.get("nationality"),
        "preferred_location": teacher.get("preferred_location"),
        "subject_specialty": teacher.get("subject_specialty"),
        "preferred_age_group": teacher.get("preferred_age_group"),
        "years_experience": teacher.get("years_experience"),
        "education": teacher.get("education"),
        "teaching_experience": teacher.get("teaching_experience"),
        "professional_experience": teacher.get("professional_experience"),
        "additional_info": teacher.get("additional_info"),
        "linkedin": teacher.get("linkedin"),
        "instagram": teacher.get("instagram"),
        "wechat_id": teacher.get("wechat_id"),
        "headshot_url": None,
        "cv_url": None,
        "video_url": None,
        "created_at": teacher.get("created_at"),
    }

    # Generate signed URLs
    try:
        if teacher.get("headshot_photo_path"):
            result["headshot_url"] = StorageService.get_teacher_headshot_url(
                teacher["id"], teacher["headshot_photo_path"]
            )
        if teacher.get("cv_path"):
            result["cv_url"] = StorageService.get_teacher_cv_url(
                teacher["id"], teacher["cv_path"]
            )
        if teacher.get("intro_video_path"):
            result["video_url"] = StorageService.get_teacher_video_url(
                teacher["id"], teacher["intro_video_path"]
            )
    except Exception as e:
        logger.error(f"Error generating URLs for teacher {teacher_id}: {e}")

    return result


# ============================================================================
# Saved Teachers (Bookmarks)
# ============================================================================

@router.post("/saved-teachers/{teacher_id}")
async def save_teacher(
    teacher_id: int,
    school: dict = Depends(get_current_school_account)
):
    """Save/bookmark a teacher"""
    supabase = get_supabase_client()

    # Check teacher exists
    teacher = supabase.table("teachers").select("id").eq("id", teacher_id).execute()
    if not teacher.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )

    # Check if already saved
    existing = supabase.table("school_saved_teachers").select("id").eq(
        "school_account_id", school["id"]
    ).eq("teacher_id", teacher_id).execute()

    if existing.data:
        return {"message": "Teacher already saved", "saved": True}

    # Save teacher
    response = supabase.table("school_saved_teachers").insert({
        "school_account_id": school["id"],
        "teacher_id": teacher_id
    }).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save teacher"
        )

    return {"message": "Teacher saved successfully", "saved": True}


@router.delete("/saved-teachers/{teacher_id}")
async def unsave_teacher(
    teacher_id: int,
    school: dict = Depends(get_current_school_account)
):
    """Remove teacher from saved list"""
    supabase = get_supabase_client()

    supabase.table("school_saved_teachers").delete().eq(
        "school_account_id", school["id"]
    ).eq("teacher_id", teacher_id).execute()

    return {"message": "Teacher removed from saved list", "saved": False}


@router.get("/saved-teachers")
async def get_saved_teachers(
    school: dict = Depends(get_current_school_account),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0)
):
    """Get list of saved teachers"""
    supabase = get_supabase_client()

    response = supabase.table("school_saved_teachers").select(
        "*, teachers(*)"
    ).eq("school_account_id", school["id"]).order(
        "created_at", desc=True
    ).range(offset, offset + limit - 1).execute()

    saved = response.data or []

    # Format based on payment status
    if school.get("has_paid"):
        # Full teacher data
        result = []
        for s in saved:
            teacher = s.get("teachers")
            if not teacher:
                continue

            teacher_data = {
                "saved_id": s["id"],
                "saved_at": s["created_at"],
                "notes": s.get("notes"),
                "teacher": {
                    "id": teacher["id"],
                    "first_name": teacher["first_name"],
                    "last_name": teacher["last_name"],
                    "email": teacher["email"],
                    "phone": teacher.get("phone"),
                    "preferred_location": teacher.get("preferred_location"),
                    "subject_specialty": teacher.get("subject_specialty"),
                    "preferred_age_group": teacher.get("preferred_age_group"),
                    "years_experience": teacher.get("years_experience"),
                    "headshot_url": None,
                }
            }

            # Generate headshot URL
            try:
                if teacher.get("headshot_photo_path"):
                    teacher_data["teacher"]["headshot_url"] = StorageService.get_teacher_headshot_url(
                        teacher["id"], teacher["headshot_photo_path"]
                    )
            except Exception as e:
                logger.error(f"Error generating headshot URL: {e}")

            result.append(teacher_data)
        return result
    else:
        # Preview only
        return [
            {
                "saved_id": s["id"],
                "saved_at": s["created_at"],
                "teacher_id": s["teacher_id"],
                "subject_specialty": s["teachers"].get("subject_specialty") if s.get("teachers") else None,
                "preferred_location": s["teachers"].get("preferred_location") if s.get("teachers") else None,
            }
            for s in saved
        ]


@router.patch("/saved-teachers/{teacher_id}/notes")
async def update_saved_teacher_notes(
    teacher_id: int,
    notes: str,
    school: dict = Depends(get_current_school_account)
):
    """Update notes for a saved teacher"""
    supabase = get_supabase_client()

    response = supabase.table("school_saved_teachers").update({
        "notes": notes
    }).eq("school_account_id", school["id"]).eq("teacher_id", teacher_id).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved teacher not found"
        )

    return {"message": "Notes updated successfully"}


# ============================================================================
# Statistics
# ============================================================================

@router.get("/stats")
async def get_school_stats(
    school: dict = Depends(get_current_school_account)
):
    """Get statistics for the school dashboard"""
    supabase = get_supabase_client()

    # Count total teachers
    teachers_count = supabase.table("teachers").select("id", count="exact").execute()

    # Count saved teachers
    saved_count = supabase.table("school_saved_teachers").select(
        "id", count="exact"
    ).eq("school_account_id", school["id"]).execute()

    return {
        "total_teachers": teachers_count.count or 0,
        "saved_teachers": saved_count.count or 0,
        "has_paid": school.get("has_paid", False),
    }


@router.get("/debug/teacher-data")
async def debug_teacher_data(
    school: dict = Depends(get_current_school_account),
    limit: int = Query(default=5, ge=1, le=20)
):
    """
    Debug endpoint to inspect teacher data format
    Shows raw values for preference fields to diagnose filter issues
    """
    if not school.get("has_paid"):
        raise HTTPException(status_code=403, detail="Paid access required")

    supabase = get_supabase_client()

    response = supabase.table("teachers").select(
        "id, preferred_location, subject_specialty, preferred_age_group"
    ).limit(limit).execute()

    teachers = response.data or []

    # Return raw data with character inspection
    debug_data = []
    for t in teachers:
        debug_data.append({
            "id": t["id"],
            "preferred_location": {
                "raw": t.get("preferred_location"),
                "repr": repr(t.get("preferred_location")),
                "type": type(t.get("preferred_location")).__name__
            },
            "subject_specialty": {
                "raw": t.get("subject_specialty"),
                "repr": repr(t.get("subject_specialty")),
                "type": type(t.get("subject_specialty")).__name__
            },
            "preferred_age_group": {
                "raw": t.get("preferred_age_group"),
                "repr": repr(t.get("preferred_age_group")),
                "type": type(t.get("preferred_age_group")).__name__
            }
        })

    return {"teachers": debug_data}

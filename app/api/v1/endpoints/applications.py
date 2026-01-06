from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.models.application import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    ApplicationWithSchoolResponse,
    AnonymousApplicationResponse
)
from app.dependencies import get_current_admin, get_current_teacher, require_payment
from app.db.supabase import get_supabase_client
from app.middleware.rate_limit import limiter
from typing import List


router = APIRouter()


@router.get("/")
async def get_all_applications(
    admin: dict = Depends(get_current_admin),
    status: str = None,
    limit: int = 50
):
    """
    Get all applications with teacher and school details (Admin only)
    """
    supabase = get_supabase_client()

    query = supabase.table("teacher_school_applications").select(
        "*, teachers(id, first_name, last_name, email, nationality), schools(id, name, city, province, school_type)"
    ).order("submitted_at", desc=True).limit(limit)

    if status:
        query = query.eq("status", status)

    response = query.execute()

    applications = []
    for app in response.data or []:
        teacher = app.get("teachers", {}) or {}
        school = app.get("schools", {}) or {}
        applications.append({
            "id": app["id"],
            "teacher_id": app["teacher_id"],
            "school_id": app["school_id"],
            "status": app["status"],
            "submitted_at": app.get("submitted_at"),
            "notes": app.get("notes"),
            "role_name": app.get("role_name"),
            "expiry_date": app.get("expiry_date"),
            "teacher": {
                "id": teacher.get("id"),
                "first_name": teacher.get("first_name", ""),
                "last_name": teacher.get("last_name", ""),
                "email": teacher.get("email", ""),
                "nationality": teacher.get("nationality", ""),
            },
            "school": {
                "id": school.get("id"),
                "name": school.get("name", ""),
                "city": school.get("city", ""),
                "province": school.get("province", ""),
                "school_type": school.get("school_type", ""),
            },
        })

    return applications


@router.post("/", response_model=List[ApplicationResponse])
@limiter.limit("30/hour")
async def submit_applications(
    request: Request,
    application_data: ApplicationCreate,
    admin: dict = Depends(get_current_admin)
):
    """
    Submit teacher application to one or more schools (Admin only)
    Creates application records for each school
    """
    supabase = get_supabase_client()

    # Verify teacher exists
    teacher_response = supabase.table("teachers").select("id").eq("id", application_data.teacher_id).execute()
    if not teacher_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )

    created_applications = []

    for school_id in application_data.school_ids:
        # Check if application already exists
        existing = supabase.table("teacher_school_applications").select("id").eq(
            "teacher_id", application_data.teacher_id
        ).eq("school_id", school_id).execute()

        if existing.data:
            continue  # Skip if already applied

        # Find matching record
        match_response = supabase.table("teacher_school_matches").select("id").eq(
            "teacher_id", application_data.teacher_id
        ).eq("school_id", school_id).single().execute()

        match_id = match_response.data["id"] if match_response.data else None

        # Create application
        app_data = {
            "teacher_id": application_data.teacher_id,
            "school_id": school_id,
            "match_id": match_id,
            "status": "pending",
            "submitted_by": admin["id"],
            "notes": application_data.notes,
            "role_name": application_data.role_name,
            "submitted_at": "now()"
        }

        # Add expiry_date if provided
        if application_data.expiry_date:
            app_data["expiry_date"] = application_data.expiry_date.isoformat()

        response = supabase.table("teacher_school_applications").insert(app_data).execute()

        if response.data:
            created_applications.append(response.data[0])

            # Update match as submitted and set role_name
            if match_id:
                match_update = {"is_submitted": True}
                if application_data.role_name:
                    match_update["role_name"] = application_data.role_name
                supabase.table("teacher_school_matches").update(match_update).eq("id", match_id).execute()

    if not created_applications:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Applications already exist for all selected schools"
        )

    return created_applications


@router.get("/teacher/{teacher_id}", response_model=List[ApplicationWithSchoolResponse])
async def get_teacher_applications_admin(
    teacher_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Get all applications for a teacher with full school details (Admin only)
    """
    supabase = get_supabase_client()

    response = supabase.table("teacher_school_applications").select(
        "*, schools(name, city, school_type, salary_range, province)"
    ).eq("teacher_id", teacher_id).order("created_at", desc=True).execute()

    applications = []
    for app in response.data or []:
        school = app.get("schools", {})
        applications.append({
            **app,
            "school_name": school.get("name", ""),
            "school_city": school.get("city", ""),
            "school_type": school.get("school_type"),
            "salary_range": school.get("salary_range"),
            "province": school.get("province"),
            "role_name": app.get("role_name"),
            "expiry_date": app.get("expiry_date"),
        })

    return applications


@router.get("/me", response_model=List[AnonymousApplicationResponse])
async def get_my_applications(
    teacher: dict = Depends(get_current_teacher)
):
    """
    Get current teacher's applications (anonymized - no school names)
    """
    supabase = get_supabase_client()

    response = supabase.table("teacher_school_applications").select(
        "*, schools(city, province, school_type, salary_range)"
    ).eq("teacher_id", teacher["id"]).order("created_at", desc=True).execute()

    applications = []
    for app in response.data or []:
        school = app.get("schools", {})
        applications.append({
            "id": app["id"],
            "city": school.get("city", ""),
            "province": school.get("province"),
            "school_type": school.get("school_type"),
            "salary_range": school.get("salary_range"),
            "status": app["status"],
            "submitted_at": app.get("submitted_at"),
            "updated_at": app["updated_at"],
            "role_name": app.get("role_name"),
            "expiry_date": app.get("expiry_date"),
        })

    return applications


@router.patch("/{application_id}", response_model=ApplicationResponse)
@limiter.limit("60/hour")
async def update_application_status(
    request: Request,
    application_id: int,
    update_data: ApplicationUpdate,
    admin: dict = Depends(get_current_admin)
):
    """
    Update application status (Admin only)
    Creates status history record
    """
    supabase = get_supabase_client()

    # Get current application
    current = supabase.table("teacher_school_applications").select("*").eq("id", application_id).single().execute()

    if not current.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )

    old_status = current.data["status"]

    # Update application
    update_dict = update_data.model_dump(exclude_unset=True)
    response = supabase.table("teacher_school_applications").update(update_dict).eq("id", application_id).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update application"
        )

    # Create status history record if status changed
    if update_data.status and old_status != update_data.status:
        history_data = {
            "application_id": application_id,
            "from_status": old_status,
            "to_status": update_data.status,
            "changed_by": admin["id"],
            "notes": update_data.notes
        }
        supabase.table("application_status_history").insert(history_data).execute()

    # Also update the match's role_name if role_name was updated
    if update_data.role_name and current.data.get("match_id"):
        supabase.table("teacher_school_matches").update({
            "role_name": update_data.role_name
        }).eq("id", current.data["match_id"]).execute()

    return response.data[0]


@router.post("/apply-to-match", response_model=ApplicationResponse)
@limiter.limit("20/hour")
async def apply_to_match(
    request: Request,
    match_id: int,
    teacher: dict = Depends(require_payment)
):
    """
    Teacher applies to a match (requires payment)
    Converts match to application
    """
    supabase = get_supabase_client()

    # Get match details and verify it belongs to this teacher
    match_response = supabase.table("teacher_school_matches").select(
        "*, schools(id)"
    ).eq("id", match_id).eq("teacher_id", teacher["id"]).single().execute()

    if not match_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found or doesn't belong to you"
        )

    school_id = match_response.data["schools"]["id"]

    # Check if already applied to this school
    existing = supabase.table("teacher_school_applications").select("id").eq(
        "teacher_id", teacher["id"]
    ).eq("school_id", school_id).execute()

    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already applied to this school"
        )

    # Create application
    app_data = {
        "teacher_id": teacher["id"],
        "school_id": school_id,
        "match_id": match_id,
        "status": "pending",
        "submitted_at": "now()"
    }

    response = supabase.table("teacher_school_applications").insert(app_data).execute()

    if response.data:
        # Mark match as submitted
        supabase.table("teacher_school_matches").update({
            "is_submitted": True
        }).eq("id", match_id).execute()

        return response.data[0]

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to create application"
    )


@router.get("/{application_id}/history")
async def get_application_history(
    application_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Get status change history for an application (Admin only)
    """
    supabase = get_supabase_client()

    response = supabase.table("application_status_history").select(
        "*, admin_users(full_name)"
    ).eq("application_id", application_id).order("created_at", desc=True).execute()

    return response.data or []

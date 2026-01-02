from fastapi import APIRouter, Depends, HTTPException, status
from app.models.application import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    ApplicationWithSchoolResponse,
    AnonymousApplicationResponse
)
from app.dependencies import get_current_admin, get_current_teacher
from app.db.supabase import get_supabase_client
from typing import List


router = APIRouter()


@router.post("/", response_model=List[ApplicationResponse])
async def submit_applications(
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
            "submitted_at": "now()"
        }

        response = supabase.table("teacher_school_applications").insert(app_data).execute()

        if response.data:
            created_applications.append(response.data[0])

            # Update match as submitted
            if match_id:
                supabase.table("teacher_school_matches").update({
                    "is_submitted": True
                }).eq("id", match_id).execute()

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
        })

    return applications


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application_status(
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

    # Create status history record
    if old_status != update_data.status:
        history_data = {
            "application_id": application_id,
            "from_status": old_status,
            "to_status": update_data.status,
            "changed_by": admin["id"],
            "notes": update_data.notes
        }
        supabase.table("application_status_history").insert(history_data).execute()

    return response.data[0]


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

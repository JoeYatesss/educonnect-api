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
import json


def parse_json_field(value):
    """Parse JSON string to dict if needed."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


router = APIRouter()


@router.get("/")
async def get_all_applications(
    admin: dict = Depends(get_current_admin),
    status: str = None,
    limit: int = 50
):
    """
    Get all applications with teacher and school/job details (Admin only)
    """
    supabase = get_supabase_client()

    query = supabase.table("teacher_school_applications").select(
        "*, teachers(id, first_name, last_name, email, nationality), "
        "schools(id, name, city, province, school_type), "
        "jobs(id, title, company, city, province, external_url, source)"
    ).order("submitted_at", desc=True).limit(limit)

    if status:
        query = query.eq("status", status)

    response = query.execute()

    applications = []
    for app in response.data or []:
        teacher = app.get("teachers", {}) or {}
        school = app.get("schools", {}) or {}
        job = app.get("jobs", {}) or {}

        # Determine if this is a job application or school application
        is_job_application = bool(app.get("job_id"))

        applications.append({
            "id": app["id"],
            "teacher_id": app["teacher_id"],
            "school_id": app["school_id"],
            "job_id": app.get("job_id"),
            "status": app["status"],
            "submitted_at": app.get("submitted_at"),
            "notes": app.get("notes"),
            "role_name": app.get("role_name"),
            "expiry_date": app.get("expiry_date"),
            "is_job_application": is_job_application,
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
            } if not is_job_application else None,
            "job": {
                "id": job.get("id"),
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "city": job.get("city", ""),
                "province": job.get("province", ""),
                "external_url": job.get("external_url", ""),
                "source": job.get("source", ""),
            } if is_job_application else None,
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
    Includes both school applications and job applications
    """
    supabase = get_supabase_client()

    response = supabase.table("teacher_school_applications").select(
        "*, schools(city, province, school_type, salary_range), "
        "jobs(city, province, location_chinese, external_url, title, company, description, "
        "application_deadline, salary, school_type, age_groups, subjects, chinese_required, "
        "qualification, contract_type, job_functions, requirements, benefits, is_new, "
        "contract_term, job_type, apply_by, recruiter_email, recruiter_phone, about_school, "
        "school_address, start_date, visa_sponsorship, accommodation_provided)"
    ).eq("teacher_id", teacher["id"]).order("created_at", desc=True).execute()

    applications = []
    for app in response.data or []:
        school = app.get("schools") or {}
        job = app.get("jobs") or {}
        is_job_application = bool(app.get("job_id"))

        # Use job data for job applications, school data for school applications
        if is_job_application:
            city = job.get("city", "")
            province = job.get("province")
            school_type = job.get("school_type")
            salary_range = job.get("salary")
            external_url = job.get("external_url")
            # Use job title as role_name for job applications (fallback to app.role_name if set)
            role_name = app.get("role_name") or job.get("title")
            # Use job application_deadline as expiry_date (fallback to app.expiry_date if set)
            expiry_date = app.get("expiry_date") or job.get("application_deadline")
            job_description = job.get("description")
        else:
            city = school.get("city", "")
            province = school.get("province")
            school_type = school.get("school_type")
            salary_range = school.get("salary_range")
            external_url = None
            role_name = app.get("role_name")
            expiry_date = app.get("expiry_date")
            job_description = None

        app_data = {
            "id": app["id"],
            "city": city,
            "province": province,
            "school_type": school_type,
            "salary_range": salary_range,
            "status": app["status"],
            "submitted_at": app.get("submitted_at"),
            "updated_at": app["updated_at"],
            "role_name": role_name,
            "expiry_date": expiry_date,
            "is_job_application": is_job_application,
            "external_url": external_url,
            "job_description": job_description,
        }

        # Add additional job fields for job applications
        if is_job_application:
            app_data.update({
                "company": job.get("company"),
                "location_chinese": job.get("location_chinese"),
                "age_groups": job.get("age_groups", []),
                "subjects": job.get("subjects", []),
                "chinese_required": job.get("chinese_required"),
                "qualification": job.get("qualification"),
                "contract_type": job.get("contract_type"),
                "job_functions": job.get("job_functions"),
                "requirements": job.get("requirements"),
                "benefits": job.get("benefits"),
                "is_new": job.get("is_new"),
                "contract_term": job.get("contract_term"),
                "job_type": job.get("job_type"),
                "apply_by": job.get("apply_by"),
                "recruiter_email": job.get("recruiter_email"),
                "recruiter_phone": job.get("recruiter_phone"),
                "about_school": job.get("about_school"),
                "school_address": parse_json_field(job.get("school_address")),
                "start_date": job.get("start_date"),
                "visa_sponsorship": job.get("visa_sponsorship"),
                "accommodation_provided": job.get("accommodation_provided"),
            })

        applications.append(app_data)

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
    Only works for school matches, not job matches
    """
    supabase = get_supabase_client()

    # Get match details and verify it belongs to this teacher
    match_response = supabase.table("teacher_school_matches").select(
        "*, schools(id), jobs(id, external_url)"
    ).eq("id", match_id).eq("teacher_id", teacher["id"]).single().execute()

    if not match_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found or doesn't belong to you"
        )

    # Check if this is a job match (external job) or school match
    job_data = match_response.data.get("jobs")
    job_id = match_response.data.get("job_id")
    schools_data = match_response.data.get("schools")
    school_id = None
    external_url = None

    if job_data or job_id:
        # This is an external job match
        job_id = job_id or (job_data.get("id") if job_data else None)
        external_url = job_data.get("external_url") if job_data else None
    elif schools_data and schools_data.get("id"):
        # This is a school match
        school_id = schools_data["id"]
    elif match_response.data.get("school_id"):
        school_id = match_response.data["school_id"]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Match has no associated school or job"
        )

    # Check if already applied to this school or job
    if school_id:
        existing = supabase.table("teacher_school_applications").select("id").eq(
            "teacher_id", teacher["id"]
        ).eq("school_id", school_id).execute()
        entity_type = "school"
    else:
        existing = supabase.table("teacher_school_applications").select("id").eq(
            "teacher_id", teacher["id"]
        ).eq("job_id", job_id).execute()
        entity_type = "job"

    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You have already applied to this {entity_type}"
        )

    # Create application
    app_data = {
        "teacher_id": teacher["id"],
        "school_id": school_id,  # Will be None for job applications
        "job_id": job_id,  # Will be None for school applications
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

        # For job applications, include external_url in response
        result = response.data[0]
        if external_url:
            result["external_url"] = external_url

        return result

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

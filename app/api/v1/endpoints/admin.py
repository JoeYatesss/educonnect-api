from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.dependencies import get_current_admin
from app.db.supabase import get_supabase_client
from app.services.storage_service import StorageService
from typing import Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats")
async def get_admin_stats(
    admin: dict = Depends(get_current_admin)
):
    """
    Get dashboard statistics for admin overview
    Returns counts of teachers, schools, applications, etc.
    """
    supabase = get_supabase_client()

    try:
        # Get total teachers count
        teachers_response = supabase.table("teachers").select("id", count="exact").execute()
        total_teachers = teachers_response.count or 0

        # Get paid teachers count
        paid_teachers_response = supabase.table("teachers").select("id", count="exact").eq("has_paid", True).execute()
        paid_teachers = paid_teachers_response.count or 0

        # Get active applications (not placed or declined)
        active_apps_response = supabase.table("teacher_school_applications").select("id", count="exact").not_.in_("status", ["placed", "declined"]).execute()
        active_applications = active_apps_response.count or 0

        # Get placed teachers count
        placed_response = supabase.table("teacher_school_applications").select("id", count="exact").eq("status", "placed").execute()
        placed_teachers = placed_response.count or 0

        # Get total schools count (from schools table)
        schools_response = supabase.table("schools").select("id", count="exact").execute()
        total_schools = schools_response.count or 0

        # Get total jobs count (from jobs table)
        jobs_response = supabase.table("jobs").select("id", count="exact").execute()
        total_jobs = jobs_response.count or 0

        # Get school jobs count (school-created jobs)
        school_jobs_response = supabase.table("school_jobs").select("id", count="exact").execute()
        total_school_jobs = school_jobs_response.count or 0

        # Get interview selections count
        selections_response = supabase.table("school_interview_selections").select("id", count="exact").execute()
        total_interview_selections = selections_response.count or 0

        # Get paid school accounts count
        paid_schools_response = supabase.table("school_accounts").select("id", count="exact").eq("has_paid", True).execute()
        paid_schools = paid_schools_response.count or 0

        return {
            "total_teachers": total_teachers,
            "paid_teachers": paid_teachers,
            "active_applications": active_applications,
            "placed_teachers": placed_teachers,
            "total_schools": total_schools,
            "total_jobs": total_jobs,
            "total_school_jobs": total_school_jobs,
            "total_interview_selections": total_interview_selections,
            "paid_schools": paid_schools
        }
    except Exception as e:
        logger.error(f"Failed to fetch admin stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch statistics"
        )


@router.get("/teachers/{teacher_id}")
async def get_teacher_details_admin(
    teacher_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Get detailed teacher profile for admin view
    Includes all profile data and file URLs
    """
    supabase = get_supabase_client()

    response = supabase.table("teachers").select("*").eq("id", teacher_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )

    teacher = response.data

    # Add file URLs if available
    try:
        if teacher.get("cv_path"):
            teacher["cv_url"] = StorageService.get_teacher_cv_url(
                teacher["id"],
                teacher["cv_path"]
            )
    except Exception as e:
        logger.error(f"Error getting CV URL: {e}")
        teacher["cv_url"] = None

    try:
        if teacher.get("headshot_photo_path"):
            teacher["headshot_url"] = StorageService.get_teacher_headshot_url(
                teacher["id"],
                teacher["headshot_photo_path"]
            )
    except Exception as e:
        logger.error(f"Error getting headshot URL: {e}")
        teacher["headshot_url"] = None

    try:
        if teacher.get("intro_video_path"):
            teacher["video_url"] = StorageService.get_teacher_video_url(
                teacher["id"],
                teacher["intro_video_path"]
            )
    except Exception as e:
        logger.error(f"Error getting video URL: {e}")
        teacher["video_url"] = None

    return teacher


@router.get("/teachers/{teacher_id}/cv-url")
async def get_teacher_cv_url(
    teacher_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Get signed URL for teacher's CV (Admin only)
    """
    supabase = get_supabase_client()

    response = supabase.table("teachers").select("cv_path").eq("id", teacher_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )

    if not response.data.get("cv_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not uploaded"
        )

    try:
        signed_url = StorageService.get_teacher_cv_url(
            teacher_id,
            response.data["cv_path"]
        )
        return {"cv_url": signed_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get CV URL: {str(e)}"
        )


@router.get("/teachers/{teacher_id}/cv-download")
async def download_teacher_cv(
    teacher_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Redirect to signed URL for teacher's CV download (Admin only)
    """
    from fastapi.responses import RedirectResponse

    supabase = get_supabase_client()

    response = supabase.table("teachers").select("cv_path").eq("id", teacher_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )

    if not response.data.get("cv_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not uploaded"
        )

    try:
        signed_url = StorageService.get_teacher_cv_url(
            teacher_id,
            response.data["cv_path"]
        )
        return RedirectResponse(url=signed_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get CV: {str(e)}"
        )


# =============================================================================
# School Invoice Request Management
# =============================================================================

@router.get("/school-invoice-requests")
async def list_school_invoice_requests(
    status_filter: str = None,
    admin: dict = Depends(get_current_admin)
):
    """
    List all school invoice/manual payment requests.
    Optionally filter by status: pending, approved, rejected
    """
    supabase = get_supabase_client()

    query = supabase.table("school_invoice_requests").select(
        "*, school_accounts(id, school_name, contact_email, contact_name, city, has_paid)"
    ).order("created_at", desc=True)

    if status_filter and status_filter in ["pending", "approved", "rejected"]:
        query = query.eq("status", status_filter)

    result = query.execute()

    return {"requests": result.data or []}


@router.get("/school-invoice-requests/{request_id}")
async def get_school_invoice_request(
    request_id: int,
    admin: dict = Depends(get_current_admin)
):
    """Get details of a specific invoice request"""
    supabase = get_supabase_client()

    result = supabase.table("school_invoice_requests").select(
        "*, school_accounts(id, school_name, contact_email, contact_name, city, has_paid, wechat_id)"
    ).eq("id", request_id).single().execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice request not found"
        )

    return result.data


@router.post("/school-invoice-requests/{request_id}/approve")
async def approve_school_invoice_request(
    request_id: int,
    admin_notes: str = None,
    admin: dict = Depends(get_current_admin)
):
    """
    Approve a school invoice request.
    This will mark the school as paid and grant them full access.
    """
    supabase = get_supabase_client()

    # Get the invoice request
    request_result = supabase.table("school_invoice_requests").select(
        "*, school_accounts(id, has_paid)"
    ).eq("id", request_id).single().execute()

    if not request_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice request not found"
        )

    invoice_request = request_result.data

    if invoice_request["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request already {invoice_request['status']}"
        )

    school_account_id = invoice_request["school_account_id"]

    # Check if school already has paid status
    if invoice_request.get("school_accounts", {}).get("has_paid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School already has paid status"
        )

    from datetime import datetime

    try:
        # Update invoice request status
        supabase.table("school_invoice_requests").update({
            "status": "approved",
            "admin_notes": admin_notes,
            "reviewed_by": admin.get("email"),
            "reviewed_at": datetime.now().isoformat()
        }).eq("id", request_id).execute()

        # Create a payment record for the manual payment
        payment_data = {
            "school_account_id": school_account_id,
            "stripe_payment_intent_id": f"manual_{request_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "stripe_customer_id": None,
            "amount": invoice_request["amount"],
            "currency": invoice_request["currency"],
            "status": "succeeded",
            "payment_method": "invoice",
            "receipt_url": None
        }
        supabase.table("school_payments").insert(payment_data).execute()

        # Update school account to mark as paid
        supabase.table("school_accounts").update({
            "has_paid": True,
            "payment_id": f"invoice_{request_id}",
            "payment_date": "now()"
        }).eq("id", school_account_id).execute()

        logger.info(f"Admin {admin.get('email')} approved invoice request {request_id} for school {school_account_id}")

        return {
            "message": "Invoice request approved. School now has full access.",
            "request_id": request_id,
            "school_account_id": school_account_id
        }

    except Exception as e:
        logger.error(f"Failed to approve invoice request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve request"
        )


@router.post("/school-invoice-requests/{request_id}/reject")
async def reject_school_invoice_request(
    request_id: int,
    admin_notes: str = None,
    admin: dict = Depends(get_current_admin)
):
    """Reject a school invoice request"""
    supabase = get_supabase_client()

    # Get the invoice request
    request_result = supabase.table("school_invoice_requests").select("*").eq("id", request_id).single().execute()

    if not request_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice request not found"
        )

    if request_result.data["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request already {request_result.data['status']}"
        )

    from datetime import datetime

    try:
        supabase.table("school_invoice_requests").update({
            "status": "rejected",
            "admin_notes": admin_notes,
            "reviewed_by": admin.get("email"),
            "reviewed_at": datetime.now().isoformat()
        }).eq("id", request_id).execute()

        logger.info(f"Admin {admin.get('email')} rejected invoice request {request_id}")

        return {
            "message": "Invoice request rejected.",
            "request_id": request_id
        }

    except Exception as e:
        logger.error(f"Failed to reject invoice request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject request"
        )


# =============================================================================
# Interview Selections Management (Real-time visibility)
# =============================================================================

@router.get("/interview-selections")
async def list_all_interview_selections(
    status_filter: str = None,
    school_account_id: int = None,
    limit: int = 50,
    offset: int = 0,
    admin: dict = Depends(get_current_admin)
):
    """
    List all interview selections across all schools.
    Provides real-time visibility into school hiring activity.
    """
    supabase = get_supabase_client()

    query = supabase.table("school_interview_selections").select(
        "*, teachers(id, first_name, last_name, email, subject_specialty, preferred_location, headshot_photo_path), "
        "school_jobs(id, title, city), school_accounts(id, school_name, city, contact_email)"
    )

    if status_filter:
        query = query.eq("status", status_filter)

    if school_account_id:
        query = query.eq("school_account_id", school_account_id)

    result = query.order("selected_at", desc=True).range(offset, offset + limit - 1).execute()

    selections = result.data or []

    # Transform to include full details with headshot URLs
    transformed = []
    for selection in selections:
        teacher = selection.get("teachers", {}) or {}
        job = selection.get("school_jobs", {}) or {}
        school = selection.get("school_accounts", {}) or {}

        # Generate headshot URL
        headshot_url = None
        try:
            if teacher.get("headshot_photo_path"):
                headshot_url = StorageService.get_teacher_headshot_url(
                    teacher["id"], teacher["headshot_photo_path"]
                )
        except Exception as e:
            logger.error(f"Error generating headshot URL: {e}")

        transformed.append({
            "id": selection["id"],
            "status": selection["status"],
            "notes": selection.get("notes"),
            "selected_at": selection["selected_at"],
            "status_updated_at": selection["status_updated_at"],
            "teacher_id": selection["teacher_id"],
            "teacher_name": f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip(),
            "teacher_email": teacher.get("email"),
            "teacher_subject": teacher.get("subject_specialty"),
            "teacher_location": teacher.get("preferred_location"),
            "teacher_headshot_url": headshot_url,
            "school_job_id": selection.get("school_job_id"),
            "job_title": job.get("title"),
            "job_city": job.get("city"),
            "school_account_id": selection["school_account_id"],
            "school_name": school.get("school_name"),
            "school_city": school.get("city"),
            "school_email": school.get("contact_email"),
        })

    return {"selections": transformed, "total": len(transformed)}


@router.get("/interview-selections/recent")
async def get_recent_interview_selections(
    hours: int = 24,
    admin: dict = Depends(get_current_admin)
):
    """
    Get interview selections from the last N hours.
    Used for real-time admin dashboard polling.
    Default: last 24 hours.
    """
    from datetime import datetime, timedelta

    supabase = get_supabase_client()

    cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

    result = supabase.table("school_interview_selections").select(
        "*, teachers(id, first_name, last_name, email, headshot_photo_path), "
        "school_jobs(id, title), school_accounts(id, school_name)"
    ).gte("selected_at", cutoff_time).order("selected_at", desc=True).execute()

    selections = result.data or []

    # Transform to include URLs and names
    transformed = []
    for selection in selections:
        teacher = selection.get("teachers", {}) or {}
        job = selection.get("school_jobs", {}) or {}
        school = selection.get("school_accounts", {}) or {}

        headshot_url = None
        try:
            if teacher.get("headshot_photo_path"):
                headshot_url = StorageService.get_teacher_headshot_url(
                    teacher["id"], teacher["headshot_photo_path"]
                )
        except:
            pass

        transformed.append({
            "id": selection["id"],
            "status": selection["status"],
            "selected_at": selection["selected_at"],
            "teacher_id": selection["teacher_id"],
            "teacher_name": f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip(),
            "teacher_email": teacher.get("email"),
            "teacher_headshot_url": headshot_url,
            "job_title": job.get("title"),
            "school_name": school.get("school_name"),
        })

    return {
        "selections": transformed,
        "count": len(transformed),
        "since_hours": hours
    }


@router.get("/interview-selections/stats")
async def get_interview_selection_stats(
    admin: dict = Depends(get_current_admin)
):
    """
    Get aggregate statistics for interview selections.
    """
    supabase = get_supabase_client()

    # Total selections
    total = supabase.table("school_interview_selections").select(
        "id", count="exact"
    ).execute()

    # By status
    all_selections = supabase.table("school_interview_selections").select("status").execute()
    status_counts = {}
    for s in all_selections.data or []:
        status = s.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    # Recent activity (last 7 days)
    from datetime import datetime, timedelta
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    recent = supabase.table("school_interview_selections").select(
        "id", count="exact"
    ).gte("selected_at", week_ago).execute()

    # Unique schools with selections
    schools_with_selections = supabase.table("school_interview_selections").select(
        "school_account_id"
    ).execute()
    unique_schools = len(set(s["school_account_id"] for s in schools_with_selections.data or []))

    return {
        "total_selections": total.count or 0,
        "by_status": status_counts,
        "last_7_days": recent.count or 0,
        "unique_schools_selecting": unique_schools
    }


@router.get("/school-jobs")
async def list_all_school_jobs(
    is_active: bool = None,
    school_account_id: int = None,
    limit: int = 50,
    offset: int = 0,
    admin: dict = Depends(get_current_admin)
):
    """
    List all school-created job postings.
    """
    supabase = get_supabase_client()

    query = supabase.table("school_jobs").select(
        "*, school_accounts(id, school_name, city)"
    )

    if is_active is not None:
        query = query.eq("is_active", is_active)

    if school_account_id:
        query = query.eq("school_account_id", school_account_id)

    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    jobs = result.data or []

    # Add match and selection counts
    transformed = []
    for job in jobs:
        school = job.get("school_accounts", {}) or {}

        # Get counts
        match_count = supabase.table("school_job_matches").select(
            "id", count="exact"
        ).eq("school_job_id", job["id"]).execute()

        selection_count = supabase.table("school_interview_selections").select(
            "id", count="exact"
        ).eq("school_job_id", job["id"]).execute()

        transformed.append({
            **job,
            "school_name": school.get("school_name"),
            "school_city": school.get("city"),
            "match_count": match_count.count or 0,
            "selection_count": selection_count.count or 0,
        })

    return {"jobs": transformed, "total": len(transformed)}

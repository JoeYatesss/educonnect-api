from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.teacher import ApplicationStatus


class ApplicationCreate(BaseModel):
    teacher_id: int
    school_ids: List[int] = Field(..., min_items=1, max_items=10)
    notes: Optional[str] = None
    role_name: Optional[str] = None
    expiry_date: Optional[datetime] = None


class ApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    notes: Optional[str] = None
    role_name: Optional[str] = None
    expiry_date: Optional[datetime] = None


class ApplicationResponse(BaseModel):
    id: int
    teacher_id: int
    school_id: Optional[int] = None  # None for job applications
    job_id: Optional[int] = None  # None for school applications
    match_id: Optional[int] = None
    status: ApplicationStatus
    submitted_by: Optional[str] = None
    notes: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    external_url: Optional[str] = None  # For job applications

    class Config:
        from_attributes = True


class ApplicationWithSchoolResponse(BaseModel):
    id: int
    teacher_id: int
    school_id: int
    school_name: str
    school_city: str
    school_type: Optional[str]
    salary_range: Optional[str]
    status: ApplicationStatus
    notes: Optional[str]
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    role_name: Optional[str] = None
    expiry_date: Optional[datetime] = None


class AnonymousApplicationResponse(BaseModel):
    """Application response for teachers (no school names)"""
    id: int
    city: str
    province: Optional[str] = None
    school_type: Optional[str] = None
    salary_range: Optional[str] = None
    status: ApplicationStatus
    submitted_at: Optional[datetime] = None
    updated_at: datetime
    role_name: Optional[str] = None
    expiry_date: Optional[datetime] = None
    is_job_application: bool = False
    external_url: Optional[str] = None

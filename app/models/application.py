from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.teacher import ApplicationStatus


class ApplicationCreate(BaseModel):
    teacher_id: int
    school_ids: List[int] = Field(..., min_items=1, max_items=10)
    notes: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus
    notes: Optional[str] = None


class ApplicationResponse(BaseModel):
    id: int
    teacher_id: int
    school_id: int
    match_id: Optional[int]
    status: ApplicationStatus
    submitted_by: Optional[str]
    notes: Optional[str]
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

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


class AnonymousApplicationResponse(BaseModel):
    """Application response for teachers (no school names)"""
    id: int
    city: str
    province: Optional[str]
    school_type: Optional[str]
    salary_range: Optional[str]
    status: ApplicationStatus
    submitted_at: Optional[datetime]
    updated_at: datetime

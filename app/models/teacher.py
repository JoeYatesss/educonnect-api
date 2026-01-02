from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    DOCUMENT_VERIFICATION = "document_verification"
    SCHOOL_MATCHING = "school_matching"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"
    OFFER_EXTENDED = "offer_extended"
    PLACED = "placed"
    DECLINED = "declined"


class TeacherCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr


class TeacherUpdate(BaseModel):
    phone: Optional[str] = Field(None, max_length=20)
    nationality: Optional[str] = Field(None, max_length=100)
    years_experience: Optional[int] = Field(None, ge=0)
    education: Optional[str] = None
    teaching_experience: Optional[str] = None
    subject_specialty: Optional[List[str]] = None
    preferred_location: Optional[List[str]] = None
    preferred_age_group: Optional[List[str]] = None
    linkedin: Optional[str] = None
    instagram: Optional[str] = None
    wechat_id: Optional[str] = None
    professional_experience: Optional[str] = None
    additional_info: Optional[str] = None


class TeacherResponse(BaseModel):
    id: int
    user_id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    nationality: Optional[str]
    years_experience: Optional[int]
    education: Optional[str]
    teaching_experience: Optional[str]
    subject_specialty: Optional[List[str]]
    preferred_location: Optional[List[str]]
    preferred_age_group: Optional[List[str]]
    intro_video_path: Optional[str]
    headshot_photo_path: Optional[str]
    cv_path: Optional[str]
    linkedin: Optional[str]
    instagram: Optional[str]
    wechat_id: Optional[str]
    professional_experience: Optional[str]
    additional_info: Optional[str]
    status: ApplicationStatus
    has_paid: bool
    payment_id: Optional[str]
    payment_date: Optional[datetime]
    stripe_customer_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

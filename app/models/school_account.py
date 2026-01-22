from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class SchoolAccountUpdate(BaseModel):
    school_name: Optional[str] = None
    city: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    wechat_id: Optional[str] = None
    annual_recruitment_volume: Optional[str] = None


class SchoolAccountResponse(BaseModel):
    id: int
    user_id: str
    school_id: Optional[int] = None
    school_name: str
    city: str
    wechat_id: Optional[str] = None
    annual_recruitment_volume: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: str
    contact_phone: Optional[str] = None
    has_paid: bool
    payment_id: Optional[str] = None
    payment_date: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    detected_country: Optional[str] = None
    detected_currency: Optional[str] = None
    preferred_currency: Optional[str] = None
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeacherPreviewResponse(BaseModel):
    id: int
    preferred_location: Optional[str] = None
    subject_specialty: Optional[str] = None
    preferred_age_group: Optional[str] = None
    years_experience: Optional[str] = None
    has_headshot: bool
    has_cv: bool
    has_video: bool


class TeacherFullResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    nationality: Optional[str] = None
    preferred_location: Optional[str] = None
    subject_specialty: Optional[str] = None
    preferred_age_group: Optional[str] = None
    years_experience: Optional[str] = None
    education: Optional[str] = None
    teaching_experience: Optional[str] = None
    professional_experience: Optional[str] = None
    additional_info: Optional[str] = None
    linkedin: Optional[str] = None
    instagram: Optional[str] = None
    wechat_id: Optional[str] = None
    headshot_url: Optional[str] = None
    cv_url: Optional[str] = None
    video_url: Optional[str] = None
    created_at: Optional[datetime] = None


class SavedTeacherResponse(BaseModel):
    saved_id: int
    saved_at: datetime
    notes: Optional[str] = None
    teacher: TeacherFullResponse

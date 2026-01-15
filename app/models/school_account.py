from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RecruitmentVolume(str, Enum):
    SMALL = "1-5"
    MEDIUM = "6-10"
    LARGE = "11-20"
    ENTERPRISE = "20+"


class SchoolAccountStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SUSPENDED = "suspended"


class SchoolAccountCreate(BaseModel):
    """Used during signup to create a school account"""
    user_id: str
    school_name: str = Field(..., min_length=1, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    contact_email: EmailStr
    wechat_id: Optional[str] = Field(None, max_length=100)
    annual_recruitment_volume: Optional[str] = None


class SchoolAccountUpdate(BaseModel):
    """Used for updating school account profile"""
    school_name: Optional[str] = Field(None, min_length=1, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    wechat_id: Optional[str] = Field(None, max_length=100)
    annual_recruitment_volume: Optional[str] = None
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=50)
    preferred_currency: Optional[str] = Field(None, max_length=3)


class SchoolAccountResponse(BaseModel):
    """Response model for school account data"""
    id: int
    user_id: str
    school_id: Optional[int]
    school_name: str
    city: str
    wechat_id: Optional[str]
    annual_recruitment_volume: Optional[str]
    contact_name: Optional[str]
    contact_email: str
    contact_phone: Optional[str]
    has_paid: bool
    payment_id: Optional[str]
    payment_date: Optional[datetime]
    stripe_customer_id: Optional[str]
    detected_country: Optional[str]
    detected_currency: Optional[str]
    preferred_currency: Optional[str]
    status: SchoolAccountStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeacherSearchFilters(BaseModel):
    """Filters for teacher search"""
    subjects: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    age_groups: Optional[List[str]] = None
    min_experience: Optional[int] = None
    max_experience: Optional[int] = None


class TeacherPreviewResponse(BaseModel):
    """Limited teacher data for unpaid schools"""
    id: int
    preferred_location: Optional[str]
    subject_specialty: Optional[str]
    preferred_age_group: Optional[str]
    years_experience: Optional[int]
    has_headshot: bool
    has_cv: bool
    has_video: bool


class TeacherFullResponse(BaseModel):
    """Full teacher data for paid schools"""
    id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    nationality: Optional[str]
    preferred_location: Optional[str]
    subject_specialty: Optional[str]
    preferred_age_group: Optional[str]
    years_experience: Optional[int]
    education: Optional[str]
    teaching_experience: Optional[str]
    professional_experience: Optional[str]
    linkedin: Optional[str]
    wechat_id: Optional[str]
    headshot_url: Optional[str]
    cv_url: Optional[str]
    video_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SavedTeacherCreate(BaseModel):
    """Used when saving/bookmarking a teacher"""
    notes: Optional[str] = None


class SavedTeacherResponse(BaseModel):
    """Response model for saved teacher data"""
    id: int
    school_account_id: int
    teacher_id: int
    notes: Optional[str]
    created_at: datetime
    teacher: Optional[dict] = None  # Will contain teacher data

    class Config:
        from_attributes = True


class SchoolPaymentResponse(BaseModel):
    """Response model for school payment data"""
    id: int
    school_account_id: int
    stripe_payment_intent_id: str
    stripe_customer_id: Optional[str]
    amount: int
    currency: str
    status: str
    payment_method: Optional[str]
    receipt_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

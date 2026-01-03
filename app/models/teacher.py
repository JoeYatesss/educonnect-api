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
    preferred_location: str = Field(..., min_length=1)  # Required: city in China
    subject_specialty: str = Field(..., min_length=1)   # Required: subject they teach
    preferred_age_group: str = Field(..., min_length=1) # Required: age groups (comma-separated)
    linkedin: Optional[str] = None  # Optional: LinkedIn profile URL


class TeacherUpdate(BaseModel):
    phone: Optional[str] = Field(None, max_length=20)
    nationality: Optional[str] = Field(None, max_length=100)
    years_experience: Optional[int] = Field(None, ge=0)
    education: Optional[str] = None
    teaching_experience: Optional[str] = None
    subject_specialty: Optional[str] = None  # Stored as VARCHAR (comma-separated if multiple)
    preferred_location: Optional[str] = None  # Stored as VARCHAR (comma-separated if multiple)
    preferred_age_group: Optional[str] = None  # Stored as VARCHAR (comma-separated if multiple)
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
    subject_specialty: Optional[str]  # Stored as VARCHAR in DB, not array
    preferred_location: Optional[str]  # Stored as VARCHAR in DB, not array
    preferred_age_group: Optional[str]  # Stored as VARCHAR in DB, not array (comma-separated)
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
    profile_completeness: Optional[int] = None  # Calculated field

    class Config:
        from_attributes = True

    @staticmethod
    def calculate_profile_completeness(teacher_data: dict) -> int:
        """
        Calculate profile completeness percentage (0-100)
        Based on required fields for a complete teacher profile
        """
        fields = [
            teacher_data.get("phone"),
            teacher_data.get("nationality"),
            teacher_data.get("years_experience"),
            teacher_data.get("education"),
            teacher_data.get("teaching_experience"),
            teacher_data.get("subject_specialty"),
            teacher_data.get("preferred_location"),
            teacher_data.get("preferred_age_group"),
            teacher_data.get("cv_path"),
            teacher_data.get("headshot_photo_path"),
        ]
        completed = sum(1 for field in fields if field not in (None, "", []))
        return round((completed / len(fields)) * 100)

from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class SchoolJobCreate(BaseModel):
    title: str
    role_type: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    school_info: Optional[str] = None
    subjects: Optional[List[str]] = None
    age_groups: Optional[List[str]] = None
    experience_required: Optional[str] = None
    chinese_required: bool = False
    qualification: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_display: Optional[str] = None
    description: Optional[str] = None
    key_responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    is_active: bool = True


class SchoolJobUpdate(BaseModel):
    title: Optional[str] = None
    role_type: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    school_info: Optional[str] = None
    subjects: Optional[List[str]] = None
    age_groups: Optional[List[str]] = None
    experience_required: Optional[str] = None
    chinese_required: Optional[bool] = None
    qualification: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_display: Optional[str] = None
    description: Optional[str] = None
    key_responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    is_active: Optional[bool] = None


class SchoolJobResponse(BaseModel):
    id: int
    school_account_id: int
    title: str
    role_type: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    school_info: Optional[str] = None
    subjects: Optional[List[str]] = None
    age_groups: Optional[List[str]] = None
    experience_required: Optional[str] = None
    chinese_required: bool
    qualification: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_display: Optional[str] = None
    description: Optional[str] = None
    key_responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SchoolJobWithStats(SchoolJobResponse):
    match_count: int = 0
    selection_count: int = 0


class TeacherMatchData(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    nationality: Optional[str] = None
    preferred_location: Optional[str] = None
    subject_specialty: Optional[str] = None
    preferred_age_group: Optional[str] = None
    years_experience: Optional[str] = None
    education: Optional[str] = None
    teaching_experience: Optional[str] = None
    professional_experience: Optional[str] = None
    linkedin: Optional[str] = None
    wechat_id: Optional[str] = None
    headshot_url: Optional[str] = None
    cv_url: Optional[str] = None
    video_url: Optional[str] = None
    has_paid: bool = False
    is_selected_for_interview: bool = False


class SchoolJobMatchResponse(BaseModel):
    id: int
    school_job_id: int
    teacher_id: int
    school_account_id: int
    match_score: float
    match_reasons: List[str] = []
    matched_at: datetime
    teacher: TeacherMatchData


class RunMatchingResponse(BaseModel):
    job_id: int
    matches_created: int
    message: str


# ============================================================================
# INTERVIEW SELECTION MODELS
# ============================================================================

class InterviewSelectionStatus(str, Enum):
    SELECTED_FOR_INTERVIEW = "selected_for_interview"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"
    OFFER_EXTENDED = "offer_extended"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_DECLINED = "offer_declined"
    WITHDRAWN = "withdrawn"


class InterviewSelectionCreate(BaseModel):
    teacher_id: int
    school_job_id: Optional[int] = None
    notes: Optional[str] = None


class InterviewSelectionUpdate(BaseModel):
    status: Optional[InterviewSelectionStatus] = None
    notes: Optional[str] = None


class InterviewSelectionResponse(BaseModel):
    id: int
    school_account_id: int
    teacher_id: int
    school_job_id: Optional[int] = None
    status: str
    notes: Optional[str] = None
    selected_at: datetime
    status_updated_at: datetime

    class Config:
        from_attributes = True


class InterviewSelectionWithDetails(InterviewSelectionResponse):
    teacher: Optional[Any] = None
    school_job: Optional[Any] = None
    school_account: Optional[Any] = None
    teacher_name: Optional[str] = None
    teacher_email: Optional[str] = None
    teacher_headshot_url: Optional[str] = None
    job_title: Optional[str] = None
    school_name: Optional[str] = None

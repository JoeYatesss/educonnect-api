from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class InterviewSelectionStatus(str, Enum):
    """Status enum for interview selections"""
    SELECTED_FOR_INTERVIEW = "selected_for_interview"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"
    OFFER_EXTENDED = "offer_extended"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_DECLINED = "offer_declined"
    WITHDRAWN = "withdrawn"


# ============================================================================
# SCHOOL JOB MODELS
# ============================================================================

class SchoolJobCreate(BaseModel):
    """Schema for creating a new school job posting"""
    title: str = Field(..., min_length=1, max_length=255)
    role_type: Optional[str] = Field(None, max_length=100)

    # Location & School Info
    location: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    province: Optional[str] = Field(None, max_length=100)
    school_info: Optional[str] = None

    # Job Requirements
    subjects: Optional[List[str]] = None
    age_groups: Optional[List[str]] = None
    experience_required: Optional[str] = Field(None, max_length=100)
    chinese_required: bool = False
    qualification: Optional[str] = None

    # Compensation
    salary_min: Optional[int] = Field(None, ge=0)
    salary_max: Optional[int] = Field(None, ge=0)
    salary_display: Optional[str] = Field(None, max_length=100)

    # Description
    description: Optional[str] = None
    key_responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None

    # Status
    is_active: bool = True


class SchoolJobUpdate(BaseModel):
    """Schema for updating a school job posting"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    role_type: Optional[str] = Field(None, max_length=100)

    # Location & School Info
    location: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    province: Optional[str] = Field(None, max_length=100)
    school_info: Optional[str] = None

    # Job Requirements
    subjects: Optional[List[str]] = None
    age_groups: Optional[List[str]] = None
    experience_required: Optional[str] = Field(None, max_length=100)
    chinese_required: Optional[bool] = None
    qualification: Optional[str] = None

    # Compensation
    salary_min: Optional[int] = Field(None, ge=0)
    salary_max: Optional[int] = Field(None, ge=0)
    salary_display: Optional[str] = Field(None, max_length=100)

    # Description
    description: Optional[str] = None
    key_responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None

    # Status
    is_active: Optional[bool] = None


class SchoolJobResponse(BaseModel):
    """Response model for school job data"""
    id: int
    school_account_id: int

    # Job Information
    title: str
    role_type: Optional[str]

    # Location & School Info
    location: Optional[str]
    city: Optional[str]
    province: Optional[str]
    school_info: Optional[str]

    # Job Requirements
    subjects: Optional[List[str]]
    age_groups: Optional[List[str]]
    experience_required: Optional[str]
    chinese_required: bool
    qualification: Optional[str]

    # Compensation
    salary_min: Optional[int]
    salary_max: Optional[int]
    salary_display: Optional[str]

    # Description
    description: Optional[str]
    key_responsibilities: Optional[str]
    requirements: Optional[str]
    benefits: Optional[str]

    # Status
    is_active: bool

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Optional computed fields
    match_count: Optional[int] = None

    class Config:
        from_attributes = True


class SchoolJobWithStats(SchoolJobResponse):
    """School job response with additional statistics"""
    match_count: int = 0
    selection_count: int = 0


# ============================================================================
# SCHOOL JOB MATCH MODELS
# ============================================================================

class SchoolJobMatchResponse(BaseModel):
    """Response model for school job match data"""
    id: int
    school_job_id: int
    teacher_id: int
    school_account_id: int
    match_score: float
    match_reasons: Optional[List[str]]
    matched_at: datetime

    # Optional teacher details (populated when joining)
    teacher: Optional[dict] = None

    class Config:
        from_attributes = True


class RunMatchingResponse(BaseModel):
    """Response for running matching on a job"""
    job_id: int
    matches_created: int
    message: str


# ============================================================================
# INTERVIEW SELECTION MODELS
# ============================================================================

class InterviewSelectionCreate(BaseModel):
    """Schema for creating an interview selection"""
    teacher_id: int
    school_job_id: Optional[int] = None
    notes: Optional[str] = None


class InterviewSelectionUpdate(BaseModel):
    """Schema for updating an interview selection"""
    status: Optional[InterviewSelectionStatus] = None
    notes: Optional[str] = None


class InterviewSelectionResponse(BaseModel):
    """Response model for interview selection data"""
    id: int
    school_account_id: int
    teacher_id: int
    school_job_id: Optional[int]
    status: InterviewSelectionStatus
    notes: Optional[str]
    selected_at: datetime
    status_updated_at: datetime

    # Optional related data (populated when joining)
    teacher: Optional[dict] = None
    school_job: Optional[dict] = None
    school_account: Optional[dict] = None

    class Config:
        from_attributes = True


class InterviewSelectionWithDetails(InterviewSelectionResponse):
    """Interview selection with full teacher and job details"""
    teacher_name: Optional[str] = None
    teacher_email: Optional[str] = None
    teacher_headshot_url: Optional[str] = None
    job_title: Optional[str] = None
    school_name: Optional[str] = None


# ============================================================================
# SCHOOL STATS MODELS
# ============================================================================

class SchoolJobStats(BaseModel):
    """Statistics for school jobs"""
    active_jobs: int
    max_jobs: int
    total_matches: int
    total_selections: int
    selections_by_status: dict

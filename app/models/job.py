from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class JobCreate(BaseModel):
    """Schema for creating a new job posting"""
    school_id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=500)
    location_chinese: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    province: Optional[str] = Field(None, max_length=100)
    salary: Optional[str] = Field(None, max_length=100)
    experience: Optional[str] = Field(None, max_length=100)
    chinese_required: bool = False
    qualification: Optional[str] = None
    contract_type: Optional[str] = Field(None, max_length=100)
    job_functions: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    age_groups: Optional[List[str]] = None
    subjects: Optional[List[str]] = None
    is_active: bool = True
    is_new: bool = True
    # Source tracking fields
    source: Optional[str] = Field(default="manual", max_length=50)
    external_id: Optional[str] = Field(None, max_length=255)
    external_url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    # TES-specific fields
    application_deadline: Optional[datetime] = None
    start_date: Optional[str] = Field(None, max_length=100)
    visa_sponsorship: Optional[bool] = None
    accommodation_provided: Optional[str] = Field(None, max_length=255)
    school_type: Optional[str] = Field(None, max_length=50)
    contract_term: Optional[str] = Field(None, max_length=50)
    # New structured fields from detail pages
    job_type: Optional[str] = Field(None, max_length=100)
    apply_by: Optional[str] = Field(None, max_length=100)
    recruiter_email: Optional[str] = Field(None, max_length=255)
    recruiter_phone: Optional[str] = Field(None, max_length=50)
    about_school: Optional[str] = None
    school_address: Optional[dict] = None  # JSON object


class JobUpdate(BaseModel):
    """Schema for updating an existing job posting"""
    school_id: Optional[int] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=500)
    location_chinese: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    province: Optional[str] = Field(None, max_length=100)
    salary: Optional[str] = Field(None, max_length=100)
    experience: Optional[str] = Field(None, max_length=100)
    chinese_required: Optional[bool] = None
    qualification: Optional[str] = None
    contract_type: Optional[str] = Field(None, max_length=100)
    job_functions: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    age_groups: Optional[List[str]] = None
    subjects: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_new: Optional[bool] = None
    # Source tracking fields
    source: Optional[str] = Field(None, max_length=50)
    external_id: Optional[str] = Field(None, max_length=255)
    external_url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    # TES-specific fields
    application_deadline: Optional[datetime] = None
    start_date: Optional[str] = Field(None, max_length=100)
    visa_sponsorship: Optional[bool] = None
    accommodation_provided: Optional[str] = Field(None, max_length=255)
    school_type: Optional[str] = Field(None, max_length=50)
    contract_term: Optional[str] = Field(None, max_length=50)
    # New structured fields from detail pages
    job_type: Optional[str] = Field(None, max_length=100)
    apply_by: Optional[str] = Field(None, max_length=100)
    recruiter_email: Optional[str] = Field(None, max_length=255)
    recruiter_phone: Optional[str] = Field(None, max_length=50)
    about_school: Optional[str] = None
    school_address: Optional[dict] = None


class JobResponse(BaseModel):
    """Schema for job posting response"""
    id: int
    school_id: Optional[int]
    title: str
    company: Optional[str]
    location: Optional[str]
    location_chinese: Optional[str]
    city: Optional[str]
    province: Optional[str]
    salary: Optional[str]
    experience: Optional[str]
    chinese_required: bool
    qualification: Optional[str]
    contract_type: Optional[str]
    job_functions: Optional[str]
    description: Optional[str]
    requirements: Optional[str]
    benefits: Optional[str]
    age_groups: Optional[List[str]]
    subjects: Optional[List[str]]
    is_active: bool
    is_new: bool
    # Source tracking fields
    source: Optional[str] = "manual"
    external_id: Optional[str] = None
    external_url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    # TES-specific fields
    application_deadline: Optional[datetime] = None
    start_date: Optional[str] = None
    visa_sponsorship: Optional[bool] = None
    accommodation_provided: Optional[str] = None
    school_type: Optional[str] = None
    contract_term: Optional[str] = None
    # New structured fields from detail pages
    job_type: Optional[str] = None
    apply_by: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_phone: Optional[str] = None
    about_school: Optional[str] = None
    school_address: Optional[dict] = None
    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

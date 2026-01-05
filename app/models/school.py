from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class SchoolType(str, Enum):
    INTERNATIONAL = "international"
    BILINGUAL = "bilingual"
    PUBLIC = "public"
    PRIVATE = "private"
    KINDERGARTEN = "kindergarten"


class SchoolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    city: str = Field(..., max_length=100)
    province: Optional[str] = Field(None, max_length=100)
    school_type: Optional[SchoolType] = None
    age_groups: Optional[List[str]] = None
    subjects_needed: Optional[List[str]] = None
    experience_required: Optional[str] = None
    chinese_required: bool = False
    salary_range: Optional[str] = None
    benefits: Optional[str] = None
    description: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    is_active: bool = True


class SchoolUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    province: Optional[str] = Field(None, max_length=100)
    school_type: Optional[SchoolType] = None
    age_groups: Optional[List[str]] = None
    subjects_needed: Optional[List[str]] = None
    experience_required: Optional[str] = None
    chinese_required: Optional[bool] = None
    salary_range: Optional[str] = None
    benefits: Optional[str] = None
    description: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    is_active: Optional[bool] = None


class SchoolResponse(BaseModel):
    id: int
    name: str
    city: str
    province: Optional[str]
    school_type: Optional[SchoolType]
    age_groups: Optional[List[str]]
    subjects_needed: Optional[List[str]]
    experience_required: Optional[str]
    chinese_required: bool
    salary_range: Optional[str]
    benefits: Optional[str]
    description: Optional[str]
    contact_name: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MatchResponse(BaseModel):
    id: int
    city: str
    province: Optional[str]
    school_type: Optional[str]
    age_groups: List[str]
    salary_range: Optional[str]
    match_score: float
    match_reasons: List[str]
    is_submitted: bool = False

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class BlogPostCreate(BaseModel):
    """Schema for creating a new blog post"""
    title: str = Field(..., min_length=1, max_length=500)
    slug: Optional[str] = Field(None, min_length=1, max_length=255)
    excerpt: Optional[str] = None
    content: str = Field(..., min_length=1)  # HTML content
    content_json: Optional[dict] = None  # TipTap JSON
    category: Optional[str] = Field(None, max_length=100)
    author: str = Field(default='EduConnect Team', max_length=255)
    featured_image: Optional[str] = Field(None, max_length=500)
    is_published: bool = False
    meta_description: Optional[str] = None
    meta_keywords: Optional[List[str]] = None


class BlogPostUpdate(BaseModel):
    """Schema for updating an existing blog post"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    slug: Optional[str] = Field(None, min_length=1, max_length=255)
    excerpt: Optional[str] = None
    content: Optional[str] = None
    content_json: Optional[dict] = None
    category: Optional[str] = Field(None, max_length=100)
    author: Optional[str] = Field(None, max_length=255)
    featured_image: Optional[str] = None
    is_published: Optional[bool] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[List[str]] = None


class BlogPostResponse(BaseModel):
    """Schema for full blog post response (admin view)"""
    id: int
    title: str
    slug: str
    excerpt: Optional[str]
    content: str
    content_json: Optional[dict]
    category: Optional[str]
    author: str
    featured_image: Optional[str]
    is_published: bool
    published_at: Optional[datetime]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BlogPostPublic(BaseModel):
    """Schema for public-facing blog post (excludes admin fields)"""
    id: int
    title: str
    slug: str
    excerpt: Optional[str]
    content: str
    category: Optional[str]
    author: str
    featured_image: Optional[str]
    published_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

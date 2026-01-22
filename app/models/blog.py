from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# SEO/AEO field types
class FAQItem(BaseModel):
    """FAQ item for AEO schema"""
    question: str
    answer: str


class Citation(BaseModel):
    """Citation/source reference"""
    title: str
    url: str
    type: Optional[str] = None  # research, website, video
    author: Optional[str] = None
    date: Optional[str] = None


class InternalLink(BaseModel):
    """Internal link to related blog post"""
    slug: str
    title: str
    context: Optional[str] = None


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
    # SEO fields
    meta_title: Optional[str] = Field(None, max_length=100)
    meta_description: Optional[str] = None
    meta_keywords: Optional[List[str]] = None
    # AEO/SEO enhancement fields
    tldr: Optional[str] = None
    faq_schema: Optional[List[dict]] = None
    schema_type: Optional[str] = Field(default='Article', max_length=50)
    citations: Optional[List[dict]] = None
    internal_links: Optional[List[dict]] = None
    featured_image_alt: Optional[str] = None


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
    # SEO fields
    meta_title: Optional[str] = Field(None, max_length=100)
    meta_description: Optional[str] = None
    meta_keywords: Optional[List[str]] = None
    # AEO/SEO enhancement fields
    tldr: Optional[str] = None
    faq_schema: Optional[List[dict]] = None
    schema_type: Optional[str] = Field(None, max_length=50)
    citations: Optional[List[dict]] = None
    internal_links: Optional[List[dict]] = None
    featured_image_alt: Optional[str] = None


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
    # SEO fields
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[List[str]] = None
    # AEO/SEO enhancement fields
    tldr: Optional[str] = None
    faq_schema: Optional[List[Any]] = None
    schema_type: Optional[str] = None
    citations: Optional[List[Any]] = None
    internal_links: Optional[List[Any]] = None
    featured_image_alt: Optional[str] = None

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
    # SEO fields for frontend rendering
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[List[str]] = None
    # AEO/SEO enhancement fields
    tldr: Optional[str] = None
    faq_schema: Optional[List[Any]] = None
    schema_type: Optional[str] = None
    citations: Optional[List[Any]] = None
    internal_links: Optional[List[Any]] = None
    featured_image_alt: Optional[str] = None

    class Config:
        from_attributes = True

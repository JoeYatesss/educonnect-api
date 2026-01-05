from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.models.blog import BlogPostCreate, BlogPostUpdate, BlogPostResponse, BlogPostPublic
from app.dependencies import get_current_admin
from app.db.supabase import get_supabase_client
from typing import List, Optional
from datetime import datetime
import re


router = APIRouter()


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text


# ==================== PUBLIC ENDPOINTS (no auth required) ====================

@router.get("/public", response_model=List[BlogPostPublic])
async def list_published_posts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    category: Optional[str] = None
):
    """
    List all published blog posts (public endpoint)

    - **limit**: Maximum number of posts to return (1-100, default 20)
    - **offset**: Number of posts to skip for pagination (default 0)
    - **category**: Filter by category (optional)
    """
    supabase = get_supabase_client()

    query = supabase.table("blog_posts").select("*").eq("is_published", True)

    if category:
        query = query.eq("category", category)

    response = query.order("published_at", desc=True).range(offset, offset + limit - 1).execute()

    return response.data or []


@router.get("/public/{slug}", response_model=BlogPostPublic)
async def get_published_post_by_slug(slug: str):
    """
    Get a single published blog post by slug (public endpoint)

    - **slug**: URL-friendly post identifier
    """
    supabase = get_supabase_client()

    response = supabase.table("blog_posts").select("*").eq("slug", slug).eq("is_published", True).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog post not found"
        )

    return response.data


# ==================== ADMIN ENDPOINTS (auth required) ====================

@router.post("/", response_model=BlogPostResponse, status_code=status.HTTP_201_CREATED)
async def create_blog_post(
    post: BlogPostCreate,
    admin: dict = Depends(get_current_admin)
):
    """
    Create a new blog post (Admin only)

    Auto-generates slug from title if not provided.
    Sets published_at timestamp if is_published is true.
    """
    supabase = get_supabase_client()

    # Auto-generate slug from title if not provided
    if not post.slug:
        post.slug = slugify(post.title)

    post_data = post.model_dump()
    post_data['created_by'] = admin['id']
    post_data['updated_by'] = admin['id']

    # Set published_at if publishing
    if post.is_published and not post_data.get('published_at'):
        post_data['published_at'] = datetime.utcnow().isoformat()

    try:
        response = supabase.table("blog_posts").insert(post_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create blog post"
            )

        return response.data[0]
    except Exception as e:
        # Handle unique constraint violation on slug
        if 'duplicate key value violates unique constraint' in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Blog post with slug '{post.slug}' already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create blog post: {str(e)}"
        )


@router.get("/", response_model=List[BlogPostResponse])
async def list_all_blog_posts(
    admin: dict = Depends(get_current_admin),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    is_published: Optional[bool] = None
):
    """
    List all blog posts including drafts (Admin only)

    - **limit**: Maximum number of posts to return (1-100, default 50)
    - **offset**: Number of posts to skip for pagination (default 0)
    - **is_published**: Filter by published status (true/false, optional)
    """
    supabase = get_supabase_client()

    query = supabase.table("blog_posts").select("*")

    if is_published is not None:
        query = query.eq("is_published", is_published)

    response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    return response.data or []


@router.get("/{post_id}", response_model=BlogPostResponse)
async def get_blog_post(
    post_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Get blog post by ID (Admin only)

    Returns full post details including draft posts.
    """
    supabase = get_supabase_client()

    response = supabase.table("blog_posts").select("*").eq("id", post_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog post not found"
        )

    return response.data


@router.patch("/{post_id}", response_model=BlogPostResponse)
async def update_blog_post(
    post_id: int,
    post_update: BlogPostUpdate,
    admin: dict = Depends(get_current_admin)
):
    """
    Update blog post (Admin only)

    Sets published_at timestamp when publishing a draft.
    Only updates fields that are provided (partial update).
    """
    supabase = get_supabase_client()

    update_dict = post_update.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    update_dict['updated_by'] = admin['id']

    # Set published_at when publishing
    if 'is_published' in update_dict and update_dict['is_published']:
        # Check if already published
        existing = supabase.table("blog_posts").select("published_at").eq("id", post_id).single().execute()
        if existing.data and not existing.data.get('published_at'):
            update_dict['published_at'] = datetime.utcnow().isoformat()

    try:
        response = supabase.table("blog_posts").update(update_dict).eq("id", post_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog post not found"
            )

        return response.data[0]
    except Exception as e:
        # Handle unique constraint violation on slug
        if 'duplicate key value violates unique constraint' in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Blog post with slug already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update blog post: {str(e)}"
        )


@router.delete("/{post_id}")
async def delete_blog_post(
    post_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    Delete blog post (Admin only)

    Permanently removes the blog post from the database.
    """
    supabase = get_supabase_client()

    response = supabase.table("blog_posts").delete().eq("id", post_id).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog post not found"
        )

    return {"message": "Blog post deleted successfully"}

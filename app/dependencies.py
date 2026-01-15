from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import get_settings
from app.db.supabase import get_supabase_client
from typing import Optional
import requests


security = HTTPBearer()


# Cache for JWKS (JSON Web Key Set)
_jwks_cache = None


def get_jwks(supabase_url: str):
    """Fetch JWKS from Supabase"""
    global _jwks_cache
    if _jwks_cache is None:
        # Remove trailing slash if present
        base_url = supabase_url.rstrip('/')
        jwks_url = f"{base_url}/auth/v1/.well-known/jwks.json"
        response = requests.get(jwks_url)
        response.raise_for_status()
        _jwks_cache = response.json()
    return _jwks_cache


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Validate JWT token and return user data
    Raises 401 if token is invalid or expired
    Supports both HS256 (legacy) and ES256 (new) tokens
    """
    settings = get_settings()
    token = credentials.credentials

    try:
        # First, try to decode with ES256 (new Supabase tokens)
        try:
            # Get the JWKS from Supabase
            jwks = get_jwks(settings.supabase_url)

            # Decode with ES256 using JWKS
            payload = jwt.decode(
                token,
                jwks,
                algorithms=["ES256"],
                audience="authenticated",
                options={"verify_aud": True}
            )
        except (JWTError, requests.RequestException):
            # If ES256 fails, try HS256 (legacy tokens)
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated"
            )

        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )

        return {
            "id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role"),
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )


async def get_current_teacher(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Get current teacher profile
    Raises 403 if user is not a teacher
    """
    supabase = get_supabase_client()

    response = supabase.table("teachers").select("*").eq("user_id", current_user["id"]).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as teacher"
        )

    return response.data


async def get_current_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Get current admin user
    Raises 403 if user is not an admin or is inactive
    """
    supabase = get_supabase_client()

    response = supabase.table("admin_users").select("*").eq("id", current_user["id"]).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as admin"
        )

    if not response.data.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is inactive"
        )

    return response.data


async def require_payment(
    teacher: dict = Depends(get_current_teacher)
) -> dict:
    """
    Ensure teacher has paid
    Raises 402 if payment is required
    """
    if not teacher.get("has_paid"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment required to access this resource"
        )

    return teacher


async def get_current_school_account(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Get current school account
    Raises 403 if user is not a school
    """
    supabase = get_supabase_client()

    response = supabase.table("school_accounts").select("*").eq("user_id", current_user["id"]).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as school"
        )

    if not response.data.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="School account is inactive"
        )

    return response.data


async def require_school_payment(
    school: dict = Depends(get_current_school_account)
) -> dict:
    """
    Ensure school has paid
    Raises 402 if payment is required
    """
    if not school.get("has_paid"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment required to access full teacher profiles"
        )

    return school

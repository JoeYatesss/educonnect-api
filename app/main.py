from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.config import get_settings
from app.middleware.rate_limit import limiter
from app.api.v1.router import api_router
import traceback


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
@limiter.limit("100/minute")
async def root(request: Request):
    return {"message": "EduConnect API", "version": "2.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler that logs errors and ensures CORS headers are returned
    """
    error_detail = str(exc)
    print(f"Unhandled exception: {error_detail}")
    print(traceback.format_exc())

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": error_detail},
    )

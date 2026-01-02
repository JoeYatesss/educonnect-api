from fastapi import APIRouter
from app.api.v1.endpoints import teachers, payments, webhooks, matching, schools, applications

api_router = APIRouter()

api_router.include_router(teachers.router, prefix="/teachers", tags=["teachers"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(matching.router, prefix="/matching", tags=["matching"])
api_router.include_router(schools.router, prefix="/schools", tags=["schools"])
api_router.include_router(applications.router, prefix="/applications", tags=["applications"])

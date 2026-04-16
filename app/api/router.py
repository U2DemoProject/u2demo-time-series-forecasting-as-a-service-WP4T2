from fastapi import APIRouter

from app.api.routes import jobs, models

api_router = APIRouter()
api_router.include_router(models.router, tags=["models"])
api_router.include_router(jobs.router, tags=["jobs"])

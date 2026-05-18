from fastapi import APIRouter

from .analyses import router as analyses_router
from .fields import router as fields_router
from .health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(analyses_router)
api_router.include_router(fields_router)

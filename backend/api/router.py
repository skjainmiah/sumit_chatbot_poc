"""Main API router that includes all sub-routers."""
from fastapi import APIRouter
from backend.api import auth, chat, admin, health, database

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(database.router, prefix="/database", tags=["Database"])

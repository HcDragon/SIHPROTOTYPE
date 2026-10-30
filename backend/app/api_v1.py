"""Mounts every module router; the app adds the /api/v1 prefix."""

from fastapi import APIRouter

from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.health.router import router as health_router
from app.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(audit_router)

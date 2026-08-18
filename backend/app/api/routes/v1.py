"""API v1 route aggregation."""

from fastapi import APIRouter

from app.api.routes.agents import router as agents_router
from app.api.routes.pem import router as pem_router
from app.api.routes.projects import router as projects_router
from app.api.routes.revisions import router as revisions_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(projects_router)
v1_router.include_router(pem_router)
v1_router.include_router(revisions_router)
v1_router.include_router(agents_router)

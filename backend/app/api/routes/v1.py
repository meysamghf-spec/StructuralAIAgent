"""API v1 route aggregation."""

from fastapi import APIRouter

from app.api.routes.agents import router as agents_router
from app.api.routes.ai_gateway import router as ai_gateway_router
from app.api.routes.code_engine import router as code_engine_router
from app.api.routes.engineering import router as engineering_router
from app.api.routes.files import router as files_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.orchestration import router as orchestration_router
from app.api.routes.pem import router as pem_router
from app.api.routes.project_memory import router as project_memory_router
from app.api.routes.projects import router as projects_router
from app.api.routes.revisions import router as revisions_router
from app.api.routes.units import router as units_router
from app.api.routes.validation import router as validation_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(projects_router)
v1_router.include_router(pem_router)
v1_router.include_router(revisions_router)
v1_router.include_router(agents_router)
v1_router.include_router(files_router)
v1_router.include_router(project_memory_router)
v1_router.include_router(units_router)
v1_router.include_router(code_engine_router)
v1_router.include_router(validation_router)
v1_router.include_router(integrations_router)
v1_router.include_router(ai_gateway_router)
v1_router.include_router(orchestration_router)
v1_router.include_router(engineering_router)

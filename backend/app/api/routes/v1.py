"""API v1 route aggregation."""

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.agent_executions import router as agent_executions_router
from app.api.routes.agents import router as agents_router
from app.api.routes.ai_gateway import router as ai_gateway_router
from app.api.routes.building import router as building_router
from app.api.routes.chat import router as chat_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.code_engine import router as code_engine_router
from app.api.routes.engineering import router as engineering_router
from app.api.routes.engineering_learning import router as engineering_learning_router
from app.api.routes.engineering_results import router as engineering_results_router
from app.api.routes.autocad import router as autocad_router
from app.api.routes.billing import router as billing_router
from app.api.routes.cad import router as cad_router
from app.api.routes.drawing_set import router as drawing_set_router
from app.api.routes.files import router as files_router
from app.api.routes.human_approval import router as human_approval_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.orchestration import router as orchestration_router
from app.api.routes.meta_agent import router as meta_agent_router
from app.api.routes.model import router as model_router
from app.api.routes.pem import router as pem_router
from app.api.routes.project_memory import router as project_memory_router
from app.api.routes.projects import router as projects_router
from app.api.routes.reports import router as reports_router
from app.api.routes.revisions import router as revisions_router
from app.api.routes.traceability import router as traceability_router
from app.api.routes.frame3d import router as frame3d_router
from app.api.routes.units import router as units_router
from app.api.routes.payments import router as payments_router
from app.api.routes.validation import router as validation_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(projects_router)
v1_router.include_router(pem_router)
v1_router.include_router(building_router)
v1_router.include_router(meta_agent_router)
v1_router.include_router(model_router)
v1_router.include_router(revisions_router)
v1_router.include_router(agents_router)
v1_router.include_router(agent_executions_router)
v1_router.include_router(files_router)
v1_router.include_router(project_memory_router)
v1_router.include_router(units_router)
v1_router.include_router(frame3d_router)
v1_router.include_router(conversations_router)
v1_router.include_router(chat_router)
v1_router.include_router(code_engine_router)
v1_router.include_router(validation_router)
v1_router.include_router(human_approval_router)
v1_router.include_router(traceability_router)
v1_router.include_router(reports_router)
v1_router.include_router(integrations_router)
v1_router.include_router(ai_gateway_router)
v1_router.include_router(orchestration_router)
v1_router.include_router(engineering_router)
v1_router.include_router(engineering_learning_router)
v1_router.include_router(engineering_results_router)
v1_router.include_router(cad_router)
v1_router.include_router(autocad_router)
v1_router.include_router(drawing_set_router)
v1_router.include_router(payments_router)
v1_router.include_router(billing_router)

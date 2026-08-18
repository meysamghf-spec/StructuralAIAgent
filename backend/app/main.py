from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Engineering AI Platform API",
        description="Phase 1 — Milestone 3 REST project API",
        version="0.3.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()

from fastapi import FastAPI

from app.api.routes import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Engineering AI Platform API",
        description="Phase 1 — Milestone 1 bootstrap",
        version="0.1.0",
    )
    app.include_router(api_router)
    return app


app = create_app()

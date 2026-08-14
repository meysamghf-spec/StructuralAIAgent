from fastapi import FastAPI

from app.api.routes import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Engineering AI Platform API",
        description="Phase 1 — Milestone 2 persistence foundation",
        version="0.2.0",
    )
    app.include_router(api_router)
    return app


app = create_app()

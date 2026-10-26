from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes import api_router
from app.infrastructure.config import get_settings


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.run_migrations_on_startup:
        from app.infrastructure.database.migrations import apply_migrations

        applied = apply_migrations(settings.resolved_database_url)
        logging.getLogger(__name__).info("Applied migrations on startup: %s", applied)
    yield


def create_app() -> FastAPI:
    _configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="SAIA API",
        description="Structural engineering AI platform API",
        version="1.0.0",
        lifespan=lifespan,
    )
    if settings.trust_proxy_headers:
        hosts = settings.trusted_proxy_host_list or ["*"]
        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()

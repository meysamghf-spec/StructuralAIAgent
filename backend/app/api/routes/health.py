from fastapi import APIRouter

from app.application.health_service import get_health_status, get_readiness_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return get_health_status()


@router.get("/ready")
def readiness_check() -> dict[str, object]:
    return get_readiness_status()

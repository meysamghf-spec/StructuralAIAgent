from fastapi import APIRouter

from app.application.health_service import get_health_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return get_health_status()

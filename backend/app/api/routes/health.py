from fastapi import APIRouter, Response, status

from app.application.health_service import get_health_status, get_readiness_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return get_health_status()


@router.get("/ready")
def readiness_check(response: Response) -> dict[str, object]:
    body = get_readiness_status()
    if body["status"] != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return body

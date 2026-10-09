from fastapi import APIRouter
from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["system"])

@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", service="swecha-ai-security-lab", environment=settings.environment)

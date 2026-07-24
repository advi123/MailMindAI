"""
MailMind AI - Health Route Handler.

Architectural Decision Rationale:
---------------------------------
1. Non-blocking Asynchronous Endpoint (`async def`): FastAPI runs async path operations
   on the main event loop, allowing high throughput for lightweight status checks.
2. Standard Schema Enforcement: Uses `response_model=HealthResponse` to validate that
   all required status fields (app_name, version, status, timestamp) are present and properly typed.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, status

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Service Health Status",
    description="Returns metadata about application identity, version, operational status, and UTC timestamp.",
    tags=["System Diagnostics"],
)
async def get_health() -> HealthResponse:
    """
    Asynchronous route handler for application health monitoring.
    """
    return HealthResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

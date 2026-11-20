import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.schemas.common import DatabaseHealth, HealthResponse

router = APIRouter(tags=["Health"])
logger = logging.getLogger("app.api.health")


class LivenessResponse(BaseModel):
    status: str
    timestamp: str
    app: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    timestamp: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def get_health_status(db: Session = Depends(get_db)) -> HealthResponse:
    """Comprehensive health check for dashboard and API clients."""
    db_connected = False
    try:
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            db_connected = True
    except Exception as exc:
        logger.warning("Database health check probe failed: %s", str(exc))
        db_connected = False

    status_str = "ok" if db_connected else "degraded"

    return HealthResponse(
        status=status_str,
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        database=DatabaseHealth(connected=db_connected),
        server_time_utc=datetime.now(timezone.utc).isoformat(),
        data_source="SIMULATED",
    )


@router.get("/health/live", response_model=LivenessResponse)
def get_liveness_probe() -> LivenessResponse:
    """
    Kubernetes / Docker liveness probe.
    Returns 200 OK immediately if the server process is responsive.
    """
    return LivenessResponse(
        status="alive",
        timestamp=datetime.now(timezone.utc).isoformat(),
        app=settings.APP_NAME,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
def get_readiness_probe(db: Session = Depends(get_db)) -> ReadinessResponse:
    """
    Kubernetes / Docker readiness probe.
    Verifies that the application can reach its database before routing traffic.
    Returns 503 Service Unavailable if database is unreachable.
    """
    try:
        result = db.execute(text("SELECT 1")).scalar()
        if result != 1:
            raise RuntimeError("Database returned unexpected scalar")
    except Exception as exc:
        logger.error("Readiness check failed - database probe failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "database": "unreachable",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    return ReadinessResponse(
        status="ready",
        database="connected",
        timestamp=datetime.now(timezone.utc).isoformat(),
        environment=settings.ENVIRONMENT,
    )

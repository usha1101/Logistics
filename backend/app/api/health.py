import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.schemas.common import DatabaseHealth, HealthResponse

router = APIRouter()
logger = logging.getLogger("app.api.health")


@router.get("/health", response_model=HealthResponse)
def get_health_status(db: Session = Depends(get_db)) -> HealthResponse:
    db_connected = False
    try:
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            db_connected = True
    except Exception as exc:
        logger.warning("Database health check probe failed: %s", str(exc))
        db_connected = False

    status = "ok" if db_connected else "degraded"

    return HealthResponse(
        status=status,
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        database=DatabaseHealth(connected=db_connected),
        server_time_utc=datetime.now(timezone.utc).isoformat(),
        data_source="SIMULATED",
    )


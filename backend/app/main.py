import logging
import time
import uuid
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import api_router
from app.api.health import get_health_status
from app.core.config import settings
from app.core.exceptions import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import (
    get_request_id,
    set_request_id,
    setup_logging,
)
from app.schemas.common import HealthResponse

logger = logging.getLogger("app.request")


def create_app() -> FastAPI:
    setup_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title="LOGIPULSE Backend API",
        version=settings.APP_VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Per-request Request-ID and structured logging middleware
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(req_id)
        request.state.request_id = req_id

        start_time = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response.headers["X-Request-ID"] = req_id

        logger.info(
            f"{request.method} {request.url.path} status={response.status_code} duration={duration_ms}ms"
        )
        return response

    # Register centralized exception handlers
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Mount API routers
    app.include_router(api_router, prefix="/api/v1")

    # Expose unprefixed /health endpoint for monitoring convenience
    app.add_api_route(
        "/health",
        get_health_status,
        methods=["GET"],
        response_model=HealthResponse,
        tags=["Health"],
    )

    return app


app = create_app()


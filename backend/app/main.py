import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import api_router
from app.api.health import (
    LivenessResponse,
    ReadinessResponse,
    get_health_status,
    get_liveness_probe,
    get_readiness_probe,
)
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
from app.core.broker import broker
from app.core.metrics import MetricsMiddleware, metrics_collector
from app.core.rate_limiter import RateLimitMiddleware
from app.core.tasks import task_manager
from app.schemas.common import HealthResponse
from app.services.simulation.manager import simulation_manager

logger = logging.getLogger("app.request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Capture the active asyncio event loop so threadpool calls can launch background simulation ticks
    loop = asyncio.get_running_loop()
    simulation_manager.set_event_loop(loop)
    task_manager.set_event_loop(loop)
    await broker.start()
    yield
    await broker.stop()


def create_app() -> FastAPI:
    setup_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title="LOGIPULSE Backend API",
        version=settings.APP_VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. API Rate Limiting Middleware
    app.add_middleware(RateLimitMiddleware)

    # 2. Prometheus Metrics Middleware
    app.add_middleware(MetricsMiddleware)

    # 3. CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 4. Per-request Request-ID and structured logging middleware
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

    # Expose unprefixed /health endpoints for container / orchestrator probes
    app.add_api_route(
        "/health",
        get_health_status,
        methods=["GET"],
        response_model=HealthResponse,
        tags=["Health"],
    )
    app.add_api_route(
        "/health/live",
        get_liveness_probe,
        methods=["GET"],
        response_model=LivenessResponse,
        tags=["Health"],
    )
    app.add_api_route(
        "/health/ready",
        get_readiness_probe,
        methods=["GET"],
        response_model=ReadinessResponse,
        tags=["Health"],
    )

    # Expose Prometheus-compatible /metrics endpoint
    @app.get("/metrics", tags=["Observability"], response_class=Response)
    def prometheus_metrics():
        exposition = metrics_collector.generate_exposition_text()
        return Response(
            content=exposition,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app


app = create_app()


import threading
import time
from collections import defaultdict
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class PrometheusMetricsCollector:
    """
    Lightweight, thread-safe Prometheus metrics collector.
    Generates standard Prometheus text exposition format (version 0.0.4)
    without requiring external daemon dependencies.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Request counts: (method, path_template, status_code) -> count
        self._request_counts: Dict[Tuple[str, str, int], int] = defaultdict(int)
        # Latency sum: (method, path_template) -> total_seconds
        self._latency_sum: Dict[Tuple[str, str], float] = defaultdict(float)
        # Latency count: (method, path_template) -> total_requests
        self._latency_count: Dict[Tuple[str, str], int] = defaultdict(int)

    def record_request(self, method: str, path: str, status_code: int, duration_seconds: float) -> None:
        with self._lock:
            # Normalize path to avoid high cardinality on dynamic IDs
            norm_path = self._normalize_path(path)
            self._request_counts[(method, norm_path, status_code)] += 1
            self._latency_sum[(method, norm_path)] += duration_seconds
            self._latency_count[(method, norm_path)] += 1

    def _normalize_path(self, path: str) -> str:
        parts = path.strip("/").split("/")
        norm_parts = []
        for part in parts:
            # Check if UUID or integer ID
            if len(part) == 36 and "-" in part:
                norm_parts.append("{id}")
            elif part.isdigit():
                norm_parts.append("{id}")
            else:
                norm_parts.append(part)
        return "/" + "/".join(norm_parts)

    def generate_exposition_text(self) -> str:
        lines = []

        # 1. logipulse_http_requests_total
        lines.append("# HELP logipulse_http_requests_total Total count of HTTP requests processed by LOGIPULSE.")
        lines.append("# TYPE logipulse_http_requests_total counter")
        with self._lock:
            for (method, path, status_code), count in sorted(self._request_counts.items()):
                lines.append(
                    f'logipulse_http_requests_total{{method="{method}",path="{path}",status="{status_code}"}} {count}'
                )

            # 2. logipulse_http_request_duration_seconds
            lines.append("# HELP logipulse_http_request_duration_seconds Total time spent processing HTTP requests.")
            lines.append("# TYPE logipulse_http_request_duration_seconds summary")
            for (method, path), total_dur in sorted(self._latency_sum.items()):
                count = self._latency_count[(method, path)]
                lines.append(
                    f'logipulse_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {total_dur:.6f}'
                )
                lines.append(
                    f'logipulse_http_request_duration_seconds_count{{method="{method}",path="{path}"}} {count}'
                )

        # 3. App metadata gauge
        lines.append("# HELP logipulse_app_info Static application metadata.")
        lines.append("# TYPE logipulse_app_info gauge")
        lines.append(
            f'logipulse_app_info{{version="{settings.APP_VERSION}",environment="{settings.ENVIRONMENT}"}} 1'
        )

        return "\n".join(lines) + "\n"


metrics_collector = PrometheusMetricsCollector()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware capturing request counts and latencies for Prometheus metrics."""

    async def dispatch(self, request: Request, call_next):
        if not settings.METRICS_ENABLED:
            return await call_next(request)

        # Don't instrument the metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration = time.perf_counter() - start

        metrics_collector.record_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_seconds=duration,
        )
        return response


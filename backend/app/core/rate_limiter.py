import math
import threading
import time
from typing import Dict, List, Optional, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings


class InMemorySlidingWindowLimiter:
    """
    Thread-safe in-memory sliding-window log rate limiter.
    Stores request timestamps per client key and path bucket.
    Automatically purges expired timestamps.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Storage: { key: [timestamp, timestamp, ...] }
        self._hits: Dict[str, List[float]] = {}
        self._last_cleanup: float = time.time()

    def _cleanup_old_keys(self, now: float) -> None:
        """Periodic cleanup to prevent unbounded memory growth."""
        if now - self._last_cleanup < 300.0:  # run every 5 minutes
            return
        self._last_cleanup = now
        expired_keys = []
        for key, timestamps in self._hits.items():
            self._hits[key] = [t for t in timestamps if now - t < 120.0]
            if not self._hits[key]:
                expired_keys.append(key)
        for key in expired_keys:
            self._hits.pop(key, None)

    def check_rate_limit(
        self,
        client_key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> Tuple[bool, int, int]:
        """
        Records a hit and checks if the rate limit is exceeded.
        Returns:
            (is_allowed: bool, remaining_requests: int, retry_after_seconds: int)
        """
        now = time.time()
        with self._lock:
            self._cleanup_old_keys(now)

            timestamps = self._hits.get(client_key, [])
            cutoff = now - window_seconds
            # Filter timestamps within current window
            valid_timestamps = [t for t in timestamps if t > cutoff]

            if len(valid_timestamps) >= limit:
                # Exceeded limit
                oldest_in_window = valid_timestamps[0]
                retry_after = max(1, math.ceil(window_seconds - (now - oldest_in_window)))
                self._hits[client_key] = valid_timestamps
                return False, 0, retry_after

            # Allowed - record this request
            valid_timestamps.append(now)
            self._hits[client_key] = valid_timestamps
            remaining = max(0, limit - len(valid_timestamps))
            return True, remaining, 0

    def reset(self) -> None:
        """Clears all rate limit state (useful in tests)."""
        with self._lock:
            self._hits.clear()


# Global in-memory rate limiter singleton
rate_limiter = InMemorySlidingWindowLimiter()


def resolve_limit_for_path(path: str) -> Optional[int]:
    """Resolves specific rate limit based on route sensitivity."""
    if path.startswith("/api/v1/auth/login"):
        return settings.RATE_LIMIT_LOGIN_PER_MINUTE
    if path.startswith("/api/v1/ai/"):
        return settings.RATE_LIMIT_AI_PER_MINUTE
    if path.startswith("/api/v1/reports/generate"):
        return settings.RATE_LIMIT_REPORT_PER_MINUTE
    return settings.RATE_LIMIT_DEFAULT_PER_MINUTE


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette middleware enforcing route-based rate limits.
    """

    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Skip rate limiting for static docs, openapi schema, and health probes
        path = request.url.path
        if path in ("/docs", "/redoc", "/openapi.json", "/metrics", "/health", "/health/live", "/health/ready"):
            return await call_next(request)

        # Determine client identifier (Forwarded header or client IP)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        limit = resolve_limit_for_path(path)
        if not limit or limit <= 0:
            return await call_next(request)

        bucket_key = f"{client_ip}:{path}"
        is_allowed, remaining, retry_after = rate_limiter.check_rate_limit(
            client_key=bucket_key,
            limit=limit,
            window_seconds=60,
        )

        if not is_allowed:
            from app.core.exceptions import format_error_payload

            content = format_error_payload(
                code="TOO_MANY_REQUESTS",
                message=f"Rate limit exceeded. Too many requests. Please retry after {retry_after} seconds.",
                details={"retry_after": retry_after, "limit": limit},
                request_id=getattr(request.state, "request_id", None),
            )
            return JSONResponse(
                status_code=429,
                content=content,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

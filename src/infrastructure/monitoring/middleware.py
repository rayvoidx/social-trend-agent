"""
FastAPI middleware for logging, metrics, and rate limiting.

Provides:
- Request/response logging with run_id
- Automatic metrics collection
- Rate limiting per IP/API key
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from .prometheus_metrics import (
    record_api_request,
    get_metrics_registry,
    PROMETHEUS_AVAILABLE,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Logging Middleware
# =============================================================================


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured logging of all requests.

    Adds run_id to each request for tracing.
    Logs request details, duration, and response status.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique run ID
        run_id = str(uuid.uuid4())[:8]
        request.state.run_id = run_id

        # Extract request info
        method = request.method
        path = request.url.path
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:100]

        start_time = time.time()

        # Log request
        logger.info(
            "Request started",
            extra={
                "run_id": run_id,
                "method": method,
                "path": path,
                "client_ip": client_ip,
                "user_agent": user_agent,
            },
        )

        try:
            response = await call_next(request)
            status_code = response.status_code
            success = status_code < 400

        except Exception as e:
            status_code = 500
            success = False
            logger.error(
                "Request failed with exception",
                extra={
                    "run_id": run_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise

        finally:
            duration = time.time() - start_time

            # Log response
            log_level = logging.INFO if success else logging.WARNING
            logger.log(
                log_level,
                "Request completed",
                extra={
                    "run_id": run_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "success": success,
                },
            )

            # Record metrics
            record_api_request(
                service="api", endpoint=path, duration_seconds=duration, success=success
            )

        # Add run_id to response headers
        response.headers["X-Run-ID"] = run_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check for forwarded headers (proxy/load balancer)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client
        if request.client:
            return request.client.host

        return "unknown"


# =============================================================================
# Metrics Middleware
# =============================================================================


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware for collecting detailed request metrics.

    Tracks:
    - Request counts by endpoint and status
    - Request duration histograms
    - Active request gauge
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not PROMETHEUS_AVAILABLE:
            return await call_next(request)

        registry = get_metrics_registry()

        # Increment active requests
        active_gauge = registry.get_metric("active_jobs")
        if active_gauge:
            active_gauge.labels(job_type="http_request").inc()

        try:
            return await call_next(request)
        finally:
            # Decrement active requests
            if active_gauge:
                active_gauge.labels(job_type="http_request").dec()

    def _normalize_path(self, path: str) -> str:
        """Normalize path to reduce cardinality."""
        # Replace IDs with placeholders
        parts = path.split("/")
        normalized = []

        for part in parts:
            if part.isdigit() or self._looks_like_uuid(part):
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/".join(normalized)

    def _looks_like_uuid(self, s: str) -> bool:
        """Check if string looks like a UUID."""
        return len(s) == 36 and s.count("-") == 4


# =============================================================================
# Rate Limiting Middleware
# =============================================================================


class RateLimitConfig:
    """Rate limiting configuration."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10,
        by_ip: bool = True,
        by_api_key: bool = True,
        whitelist: Optional[list] = None,
        blacklist: Optional[list] = None,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        self.by_ip = by_ip
        self.by_api_key = by_api_key
        self.whitelist = whitelist or []
        self.blacklist = blacklist or []


class RateLimiter:
    """
    Token bucket rate limiter.

    Supports:
    - Per-IP limiting
    - Per-API-key limiting
    - Configurable time windows
    - Whitelist/blacklist
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config
        # Store: {identifier: [(timestamp, count), ...]}
        self._minute_buckets: Dict[str, list] = defaultdict(list)
        self._hour_buckets: Dict[str, list] = defaultdict(list)

    def is_allowed(self, identifier: str) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed.

        Returns:
            (allowed, info_dict)
        """
        # Check whitelist
        if identifier in self.config.whitelist:
            return True, {"whitelisted": True}

        # Check blacklist
        if identifier in self.config.blacklist:
            return False, {"blacklisted": True, "retry_after": 3600}

        now = time.time()

        # Clean old entries and count
        minute_count = self._count_requests(self._minute_buckets[identifier], now - 60)
        hour_count = self._count_requests(self._hour_buckets[identifier], now - 3600)

        # Check limits
        if minute_count >= self.config.requests_per_minute:
            retry_after = 60 - (now - self._minute_buckets[identifier][0][0])
            return False, {
                "limit": "minute",
                "current": minute_count,
                "max": self.config.requests_per_minute,
                "retry_after": max(1, int(retry_after)),
            }

        if hour_count >= self.config.requests_per_hour:
            retry_after = 3600 - (now - self._hour_buckets[identifier][0][0])
            return False, {
                "limit": "hour",
                "current": hour_count,
                "max": self.config.requests_per_hour,
                "retry_after": max(1, int(retry_after)),
            }

        # Record request
        self._minute_buckets[identifier].append((now, 1))
        self._hour_buckets[identifier].append((now, 1))

        return True, {
            "minute_remaining": self.config.requests_per_minute - minute_count - 1,
            "hour_remaining": self.config.requests_per_hour - hour_count - 1,
        }

    def _count_requests(self, bucket: list, cutoff: float) -> int:
        """Count requests after cutoff time and clean old entries."""
        # Remove old entries
        while bucket and bucket[0][0] < cutoff:
            bucket.pop(0)

        return sum(count for _, count in bucket)

    def get_stats(self, identifier: str) -> Dict[str, Any]:
        """Get current stats for an identifier."""
        now = time.time()

        minute_count = self._count_requests(self._minute_buckets[identifier], now - 60)
        hour_count = self._count_requests(self._hour_buckets[identifier], now - 3600)

        return {
            "identifier": identifier,
            "minute": {
                "used": minute_count,
                "limit": self.config.requests_per_minute,
                "remaining": self.config.requests_per_minute - minute_count,
            },
            "hour": {
                "used": hour_count,
                "limit": self.config.requests_per_hour,
                "remaining": self.config.requests_per_hour - hour_count,
            },
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.

    Limits requests per IP and/or API key.
    Returns 429 Too Many Requests when limit exceeded.
    """

    def __init__(self, app, config: Optional[RateLimitConfig] = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.limiter = RateLimiter(self.config)

        # Paths to exclude from rate limiting
        self.exclude_paths = {
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
            "/redoc",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Get identifier
        identifier = self._get_identifier(request)

        # Check rate limit
        allowed, info = self.limiter.is_allowed(identifier)

        if not allowed:
            # Record rate limit hit
            from .prometheus_metrics import record_api_request

            record_api_request(
                service="api",
                endpoint=request.url.path,
                duration_seconds=0,
                success=False,
                rate_limited=True,
            )

            # Log
            logger.warning(
                "Rate limit exceeded",
                extra={"identifier": identifier, "path": request.url.path, "info": info},
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded ({info.get('limit', 'unknown')} limit)",
                    "retry_after": info.get("retry_after", 60),
                },
                headers={
                    "Retry-After": str(info.get("retry_after", 60)),
                    "X-RateLimit-Limit": str(info.get("max", 0)),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit-Minute"] = str(self.config.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(info.get("minute_remaining", 0))
        response.headers["X-RateLimit-Limit-Hour"] = str(self.config.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(info.get("hour_remaining", 0))

        return response

    def _get_identifier(self, request: Request) -> str:
        """Get identifier for rate limiting."""
        identifiers = []

        # By API key
        if self.config.by_api_key:
            api_key = request.headers.get("x-api-key") or request.headers.get(
                "authorization", ""
            ).replace("Bearer ", "")
            if api_key:
                identifiers.append(f"key:{api_key[:8]}")

        # By IP
        if self.config.by_ip:
            ip = self._get_client_ip(request)
            identifiers.append(f"ip:{ip}")

        return "|".join(identifiers) if identifiers else "anonymous"

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host

        return "unknown"


# =============================================================================
# Structured Logging Setup
# =============================================================================


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "run_id"):
            log_data["run_id"] = record.run_id
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "client_ip"):
            log_data["client_ip"] = record.client_ip
        if hasattr(record, "error"):
            log_data["error"] = record.error
        if hasattr(record, "error_type"):
            log_data["error_type"] = record.error_type

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_structured_logging(level: str = "INFO", json_format: bool = True):
    """Set up structured logging for the application."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    handler = logging.StreamHandler()

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

    root_logger.addHandler(handler)

    logger.info("Structured logging configured", extra={"json_format": json_format})


# =============================================================================
# FastAPI Setup Helper
# =============================================================================


def setup_middleware(
    app,
    enable_logging: bool = True,
    enable_metrics: bool = True,
    enable_rate_limit: bool = True,
    rate_limit_config: Optional[RateLimitConfig] = None,
):
    """
    Set up all middleware for a FastAPI app.

    Args:
        app: FastAPI application
        enable_logging: Enable logging middleware
        enable_metrics: Enable metrics middleware
        enable_rate_limit: Enable rate limiting middleware
        rate_limit_config: Custom rate limit configuration
    """
    if enable_rate_limit:
        app.add_middleware(RateLimitMiddleware, config=rate_limit_config or RateLimitConfig())

    if enable_metrics:
        app.add_middleware(MetricsMiddleware)

    if enable_logging:
        app.add_middleware(LoggingMiddleware)

    logger.info(
        "Middleware configured",
        extra={
            "logging": enable_logging,
            "metrics": enable_metrics,
            "rate_limit": enable_rate_limit,
        },
    )

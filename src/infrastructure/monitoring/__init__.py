"""
Monitoring and observability infrastructure.

Provides:
- Prometheus metrics
- Request logging middleware
- Rate limiting middleware
- Performance monitoring and aggregation
"""
from .prometheus_metrics import (
    get_metrics_registry,
    MetricsRegistry,
    record_llm_request,
    record_api_request,
    record_agent_run,
    record_vector_operation,
    record_cache_operation,
    record_workflow_transition,
    record_items_collected,
    set_active_jobs,
    set_queue_size,
    set_app_info,
    track_llm_call,
    track_api_call,
    track_agent_run,
    track_operation,
    get_metrics,
    get_metrics_content_type,
    PROMETHEUS_AVAILABLE,
)
from .middleware import (
    LoggingMiddleware,
    MetricsMiddleware,
    RateLimitMiddleware,
    RateLimitConfig,
    RateLimiter,
    JSONFormatter,
    setup_structured_logging,
    setup_middleware,
)
# Import from metrics.py (renamed from monitoring.py to avoid name conflict)
from ..metrics import (
    PerformanceMetrics,
    PerformanceMonitor,
    MetricsAggregator,
)

__all__ = [
    # Metrics
    "get_metrics_registry",
    "MetricsRegistry",
    "record_llm_request",
    "record_api_request",
    "record_agent_run",
    "record_vector_operation",
    "record_cache_operation",
    "record_workflow_transition",
    "record_items_collected",
    "set_active_jobs",
    "set_queue_size",
    "set_app_info",
    "track_llm_call",
    "track_api_call",
    "track_agent_run",
    "track_operation",
    "get_metrics",
    "get_metrics_content_type",
    "PROMETHEUS_AVAILABLE",
    # Middleware
    "LoggingMiddleware",
    "MetricsMiddleware",
    "RateLimitMiddleware",
    "RateLimitConfig",
    "RateLimiter",
    "JSONFormatter",
    "setup_structured_logging",
    "setup_middleware",
    # Performance monitoring
    "PerformanceMetrics",
    "PerformanceMonitor",
    "MetricsAggregator",
]

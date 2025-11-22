"""
Prometheus metrics for monitoring.

Provides metrics for:
- LLM API calls (latency, tokens, cost)
- External API calls
- Agent execution
- System resources
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Info,
        CollectorRegistry,
        generate_latest,
        CONTENT_TYPE_LATEST,
        multiprocess,
        REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# Metrics Registry
# =============================================================================

class MetricsRegistry:
    """Central registry for all application metrics."""

    _instance: Optional["MetricsRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._metrics: Dict[str, Any] = {}

        if not PROMETHEUS_AVAILABLE:
            logger.warning("prometheus_client not available. Metrics will be no-op.")
            return

        self._init_metrics()

    def _init_metrics(self):
        """Initialize all metrics."""

        # =====================================================================
        # LLM Metrics
        # =====================================================================

        self._metrics["llm_requests_total"] = Counter(
            "llm_requests_total",
            "Total number of LLM API requests",
            ["provider", "model", "status"]
        )

        self._metrics["llm_request_duration_seconds"] = Histogram(
            "llm_request_duration_seconds",
            "LLM API request duration in seconds",
            ["provider", "model"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
        )

        self._metrics["llm_tokens_total"] = Counter(
            "llm_tokens_total",
            "Total number of tokens used",
            ["provider", "model", "token_type"]
        )

        self._metrics["llm_cost_total"] = Counter(
            "llm_cost_total",
            "Total cost of LLM API calls in USD",
            ["provider", "model"]
        )

        self._metrics["llm_errors_total"] = Counter(
            "llm_errors_total",
            "Total number of LLM API errors",
            ["provider", "model", "error_type"]
        )

        # =====================================================================
        # External API Metrics
        # =====================================================================

        self._metrics["api_requests_total"] = Counter(
            "api_requests_total",
            "Total number of external API requests",
            ["service", "endpoint", "status"]
        )

        self._metrics["api_request_duration_seconds"] = Histogram(
            "api_request_duration_seconds",
            "External API request duration in seconds",
            ["service", "endpoint"],
            buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        )

        self._metrics["api_rate_limit_hits"] = Counter(
            "api_rate_limit_hits_total",
            "Number of rate limit hits",
            ["service"]
        )

        # =====================================================================
        # Agent Metrics
        # =====================================================================

        self._metrics["agent_runs_total"] = Counter(
            "agent_runs_total",
            "Total number of agent executions",
            ["agent_name", "status"]
        )

        self._metrics["agent_run_duration_seconds"] = Histogram(
            "agent_run_duration_seconds",
            "Agent execution duration in seconds",
            ["agent_name"],
            buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
        )

        self._metrics["agent_steps_total"] = Counter(
            "agent_steps_total",
            "Total number of agent steps executed",
            ["agent_name", "step_name"]
        )

        # =====================================================================
        # RAG/Vector Store Metrics
        # =====================================================================

        self._metrics["vector_operations_total"] = Counter(
            "vector_operations_total",
            "Total vector store operations",
            ["operation", "namespace", "status"]
        )

        self._metrics["vector_operation_duration_seconds"] = Histogram(
            "vector_operation_duration_seconds",
            "Vector store operation duration",
            ["operation", "namespace"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
        )

        self._metrics["retrieval_results_count"] = Histogram(
            "retrieval_results_count",
            "Number of results returned from retrieval",
            ["namespace"],
            buckets=(0, 1, 5, 10, 20, 50, 100)
        )

        # =====================================================================
        # Cache Metrics
        # =====================================================================

        self._metrics["cache_operations_total"] = Counter(
            "cache_operations_total",
            "Total cache operations",
            ["operation", "status"]
        )

        self._metrics["cache_hit_ratio"] = Gauge(
            "cache_hit_ratio",
            "Cache hit ratio",
            ["cache_name"]
        )

        # =====================================================================
        # Workflow Metrics
        # =====================================================================

        self._metrics["workflow_items_total"] = Counter(
            "workflow_items_total",
            "Total workflow items created",
            ["item_type", "status"]
        )

        self._metrics["workflow_transitions_total"] = Counter(
            "workflow_transitions_total",
            "Total workflow state transitions",
            ["from_status", "to_status"]
        )

        self._metrics["workflow_review_duration_seconds"] = Histogram(
            "workflow_review_duration_seconds",
            "Time spent in review",
            ["item_type"],
            buckets=(60, 300, 900, 1800, 3600, 7200, 14400)
        )

        # =====================================================================
        # Data Collection Metrics
        # =====================================================================

        self._metrics["items_collected_total"] = Counter(
            "items_collected_total",
            "Total items collected from sources",
            ["source", "item_type"]
        )

        self._metrics["items_processed_total"] = Counter(
            "items_processed_total",
            "Total items processed",
            ["stage", "status"]
        )

        self._metrics["duplicates_detected_total"] = Counter(
            "duplicates_detected_total",
            "Total duplicate items detected",
            ["source"]
        )

        # =====================================================================
        # System Metrics
        # =====================================================================

        self._metrics["active_jobs"] = Gauge(
            "active_jobs",
            "Number of active jobs",
            ["job_type"]
        )

        self._metrics["queue_size"] = Gauge(
            "queue_size",
            "Size of processing queues",
            ["queue_name"]
        )

        # App info
        self._metrics["app_info"] = Info(
            "app",
            "Application information"
        )

        logger.info("Prometheus metrics initialized")

    def get_metric(self, name: str) -> Any:
        """Get a metric by name."""
        return self._metrics.get(name)


# =============================================================================
# Global Registry Instance
# =============================================================================

_registry: Optional[MetricsRegistry] = None


def get_metrics_registry() -> MetricsRegistry:
    """Get the global metrics registry."""
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry


# =============================================================================
# Metric Helper Functions
# =============================================================================

def record_llm_request(
    provider: str,
    model: str,
    duration_seconds: float,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    success: bool = True,
    error_type: Optional[str] = None
):
    """Record metrics for an LLM request."""
    registry = get_metrics_registry()

    if not PROMETHEUS_AVAILABLE:
        return

    status = "success" if success else "error"

    # Request count
    counter = registry.get_metric("llm_requests_total")
    if counter:
        counter.labels(provider=provider, model=model, status=status).inc()

    # Duration
    histogram = registry.get_metric("llm_request_duration_seconds")
    if histogram:
        histogram.labels(provider=provider, model=model).observe(duration_seconds)

    # Tokens
    token_counter = registry.get_metric("llm_tokens_total")
    if token_counter:
        token_counter.labels(provider=provider, model=model, token_type="input").inc(input_tokens)
        token_counter.labels(provider=provider, model=model, token_type="output").inc(output_tokens)

    # Cost
    cost_counter = registry.get_metric("llm_cost_total")
    if cost_counter:
        cost_counter.labels(provider=provider, model=model).inc(cost_usd)

    # Errors
    if not success and error_type:
        error_counter = registry.get_metric("llm_errors_total")
        if error_counter:
            error_counter.labels(provider=provider, model=model, error_type=error_type).inc()


def record_api_request(
    service: str,
    endpoint: str,
    duration_seconds: float,
    success: bool = True,
    rate_limited: bool = False
):
    """Record metrics for an external API request."""
    registry = get_metrics_registry()

    if not PROMETHEUS_AVAILABLE:
        return

    status = "success" if success else "error"

    # Request count
    counter = registry.get_metric("api_requests_total")
    if counter:
        counter.labels(service=service, endpoint=endpoint, status=status).inc()

    # Duration
    histogram = registry.get_metric("api_request_duration_seconds")
    if histogram:
        histogram.labels(service=service, endpoint=endpoint).observe(duration_seconds)

    # Rate limit
    if rate_limited:
        rate_counter = registry.get_metric("api_rate_limit_hits")
        if rate_counter:
            rate_counter.labels(service=service).inc()


def record_agent_run(
    agent_name: str,
    duration_seconds: float,
    success: bool = True,
    steps: Optional[Dict[str, int]] = None
):
    """Record metrics for an agent run."""
    registry = get_metrics_registry()

    if not PROMETHEUS_AVAILABLE:
        return

    status = "success" if success else "error"

    # Run count
    counter = registry.get_metric("agent_runs_total")
    if counter:
        counter.labels(agent_name=agent_name, status=status).inc()

    # Duration
    histogram = registry.get_metric("agent_run_duration_seconds")
    if histogram:
        histogram.labels(agent_name=agent_name).observe(duration_seconds)

    # Steps
    if steps:
        step_counter = registry.get_metric("agent_steps_total")
        if step_counter:
            for step_name, count in steps.items():
                step_counter.labels(agent_name=agent_name, step_name=step_name).inc(count)


def record_vector_operation(
    operation: str,
    namespace: str,
    duration_seconds: float,
    success: bool = True,
    results_count: int = 0
):
    """Record metrics for vector store operations."""
    registry = get_metrics_registry()

    if not PROMETHEUS_AVAILABLE:
        return

    status = "success" if success else "error"

    # Operation count
    counter = registry.get_metric("vector_operations_total")
    if counter:
        counter.labels(operation=operation, namespace=namespace, status=status).inc()

    # Duration
    histogram = registry.get_metric("vector_operation_duration_seconds")
    if histogram:
        histogram.labels(operation=operation, namespace=namespace).observe(duration_seconds)

    # Results count (for queries)
    if operation == "query" and results_count >= 0:
        results_hist = registry.get_metric("retrieval_results_count")
        if results_hist:
            results_hist.labels(namespace=namespace).observe(results_count)


def record_cache_operation(
    operation: str,
    hit: bool = False
):
    """Record cache operation metrics."""
    registry = get_metrics_registry()

    if not PROMETHEUS_AVAILABLE:
        return

    status = "hit" if hit else "miss"

    counter = registry.get_metric("cache_operations_total")
    if counter:
        counter.labels(operation=operation, status=status).inc()


def record_workflow_transition(
    from_status: str,
    to_status: str,
    item_type: str
):
    """Record workflow state transition."""
    registry = get_metrics_registry()

    if not PROMETHEUS_AVAILABLE:
        return

    counter = registry.get_metric("workflow_transitions_total")
    if counter:
        counter.labels(from_status=from_status, to_status=to_status).inc()


def record_items_collected(
    source: str,
    item_type: str,
    count: int = 1
):
    """Record collected items."""
    registry = get_metrics_registry()

    if not PROMETHEUS_AVAILABLE:
        return

    counter = registry.get_metric("items_collected_total")
    if counter:
        counter.labels(source=source, item_type=item_type).inc(count)


def set_active_jobs(job_type: str, count: int):
    """Set number of active jobs."""
    registry = get_metrics_registry()

    if not PROMETHEUS_AVAILABLE:
        return

    gauge = registry.get_metric("active_jobs")
    if gauge:
        gauge.labels(job_type=job_type).set(count)


def set_queue_size(queue_name: str, size: int):
    """Set queue size."""
    registry = get_metrics_registry()

    if not PROMETHEUS_AVAILABLE:
        return

    gauge = registry.get_metric("queue_size")
    if gauge:
        gauge.labels(queue_name=queue_name).set(size)


def set_app_info(version: str, environment: str, **kwargs):
    """Set application info."""
    registry = get_metrics_registry()

    if not PROMETHEUS_AVAILABLE:
        return

    info = registry.get_metric("app_info")
    if info:
        info.info({
            "version": version,
            "environment": environment,
            **kwargs
        })


# =============================================================================
# Decorators
# =============================================================================

def track_llm_call(provider: str, model: str):
    """Decorator to track LLM API calls."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_type = None
            input_tokens = 0
            output_tokens = 0
            cost = 0.0

            try:
                result = func(*args, **kwargs)

                # Try to extract usage info from result
                if isinstance(result, dict):
                    usage = result.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)

                return result

            except Exception as e:
                success = False
                error_type = type(e).__name__
                raise

            finally:
                duration = time.time() - start_time
                record_llm_request(
                    provider=provider,
                    model=model,
                    duration_seconds=duration,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost,
                    success=success,
                    error_type=error_type
                )

        return wrapper
    return decorator


def track_api_call(service: str, endpoint: str):
    """Decorator to track external API calls."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            rate_limited = False

            try:
                result = func(*args, **kwargs)
                return result

            except Exception as e:
                success = False
                # Check for rate limit errors
                if "rate" in str(e).lower() or "429" in str(e):
                    rate_limited = True
                raise

            finally:
                duration = time.time() - start_time
                record_api_request(
                    service=service,
                    endpoint=endpoint,
                    duration_seconds=duration,
                    success=success,
                    rate_limited=rate_limited
                )

        return wrapper
    return decorator


def track_agent_run(agent_name: str):
    """Decorator to track agent execution."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True

            try:
                result = func(*args, **kwargs)
                return result

            except Exception as e:
                success = False
                raise

            finally:
                duration = time.time() - start_time
                record_agent_run(
                    agent_name=agent_name,
                    duration_seconds=duration,
                    success=success
                )

        return wrapper
    return decorator


@contextmanager
def track_operation(
    operation_type: str,
    labels: Dict[str, str],
    metric_prefix: str = "custom"
):
    """Context manager for tracking arbitrary operations."""
    start_time = time.time()
    success = True

    try:
        yield
    except Exception:
        success = False
        raise
    finally:
        duration = time.time() - start_time
        logger.debug(
            f"{operation_type} completed",
            extra={
                "duration": duration,
                "success": success,
                **labels
            }
        )


# =============================================================================
# Metrics Export
# =============================================================================

def get_metrics() -> bytes:
    """Get metrics in Prometheus format."""
    if not PROMETHEUS_AVAILABLE:
        return b""

    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Get content type for metrics endpoint."""
    if not PROMETHEUS_AVAILABLE:
        return "text/plain"

    return CONTENT_TYPE_LATEST

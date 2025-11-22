"""
Unit tests for monitoring and metrics.
"""
import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock

from src.infrastructure.monitoring.middleware import (
    RateLimiter,
    RateLimitConfig,
    JSONFormatter,
)
from src.infrastructure.monitoring.prometheus_metrics import (
    MetricsRegistry,
    PROMETHEUS_AVAILABLE,
)


class TestRateLimitConfig:
    """Test rate limit configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RateLimitConfig()

        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_size == 10
        assert config.by_ip is True
        assert config.by_api_key is True
        assert config.whitelist == []
        assert config.blacklist == []

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=500,
            burst_size=5,
            whitelist=["admin"],
            blacklist=["banned"]
        )

        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
        assert config.whitelist == ["admin"]
        assert config.blacklist == ["banned"]


class TestRateLimiter:
    """Test rate limiter functionality."""

    def test_allow_requests_within_limit(self):
        """Test requests within limit are allowed."""
        config = RateLimitConfig(requests_per_minute=5)
        limiter = RateLimiter(config)

        for i in range(5):
            allowed, info = limiter.is_allowed("test_client")
            assert allowed, f"Request {i+1} should be allowed"

    def test_block_requests_over_minute_limit(self):
        """Test requests over minute limit are blocked."""
        config = RateLimitConfig(requests_per_minute=3, requests_per_hour=1000)
        limiter = RateLimiter(config)

        # Use up the limit
        for _ in range(3):
            limiter.is_allowed("test_client")

        # 4th request should be blocked
        allowed, info = limiter.is_allowed("test_client")
        assert not allowed
        assert info.get("limit") == "minute"
        assert "retry_after" in info

    def test_block_requests_over_hour_limit(self):
        """Test requests over hour limit are blocked."""
        config = RateLimitConfig(requests_per_minute=100, requests_per_hour=5)
        limiter = RateLimiter(config)

        # Use up the hour limit
        for _ in range(5):
            limiter.is_allowed("test_client")

        # Next request should be blocked by hour limit
        allowed, info = limiter.is_allowed("test_client")
        assert not allowed
        assert info.get("limit") == "hour"

    def test_whitelist_bypass(self):
        """Test whitelisted clients bypass limits."""
        config = RateLimitConfig(
            requests_per_minute=1,
            whitelist=["admin_client"]
        )
        limiter = RateLimiter(config)

        # Should always be allowed
        for _ in range(10):
            allowed, info = limiter.is_allowed("admin_client")
            assert allowed
            assert info.get("whitelisted") is True

    def test_blacklist_block(self):
        """Test blacklisted clients are always blocked."""
        config = RateLimitConfig(blacklist=["banned_client"])
        limiter = RateLimiter(config)

        allowed, info = limiter.is_allowed("banned_client")
        assert not allowed
        assert info.get("blacklisted") is True

    def test_different_clients_independent(self):
        """Test different clients have independent limits."""
        config = RateLimitConfig(requests_per_minute=2)
        limiter = RateLimiter(config)

        # Client A uses up limit
        limiter.is_allowed("client_a")
        limiter.is_allowed("client_a")
        allowed_a, _ = limiter.is_allowed("client_a")
        assert not allowed_a

        # Client B should still have quota
        allowed_b, _ = limiter.is_allowed("client_b")
        assert allowed_b

    def test_get_stats(self):
        """Test getting client stats."""
        config = RateLimitConfig(requests_per_minute=10, requests_per_hour=100)
        limiter = RateLimiter(config)

        # Make some requests
        for _ in range(3):
            limiter.is_allowed("test_client")

        stats = limiter.get_stats("test_client")

        assert stats["identifier"] == "test_client"
        assert stats["minute"]["used"] == 3
        assert stats["minute"]["remaining"] == 7
        assert stats["hour"]["used"] == 3
        assert stats["hour"]["remaining"] == 97

    def test_remaining_counts_decrease(self):
        """Test remaining counts decrease correctly."""
        config = RateLimitConfig(requests_per_minute=5)
        limiter = RateLimiter(config)

        allowed, info = limiter.is_allowed("test_client")
        assert allowed
        assert info["minute_remaining"] == 4

        allowed, info = limiter.is_allowed("test_client")
        assert allowed
        assert info["minute_remaining"] == 3


class TestJSONFormatter:
    """Test JSON log formatter."""

    def test_basic_format(self):
        """Test basic log formatting."""
        import logging
        import json

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_format_with_extra_fields(self):
        """Test formatting with extra fields."""
        import logging
        import json

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Request completed",
            args=(),
            exc_info=None
        )
        record.run_id = "abc123"
        record.method = "GET"
        record.path = "/api/test"
        record.status_code = 200
        record.duration_ms = 123.45

        result = formatter.format(record)
        data = json.loads(result)

        assert data["run_id"] == "abc123"
        assert data["method"] == "GET"
        assert data["path"] == "/api/test"
        assert data["status_code"] == 200
        assert data["duration_ms"] == 123.45


class TestMetricsRegistry:
    """Test metrics registry."""

    def test_registry_singleton(self):
        """Test registry is a singleton."""
        registry1 = MetricsRegistry()
        registry2 = MetricsRegistry()
        assert registry1 is registry2

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not installed")
    def test_get_metric(self):
        """Test getting a metric by name."""
        registry = MetricsRegistry()

        counter = registry.get_metric("llm_requests_total")
        assert counter is not None

        # Non-existent metric
        metric = registry.get_metric("non_existent_metric")
        assert metric is None


class TestPrometheusMetricFunctions:
    """Test Prometheus metric helper functions."""

    def test_record_llm_request(self):
        """Test recording LLM request metrics."""
        from src.infrastructure.monitoring.prometheus_metrics import record_llm_request

        # Should not raise even without Prometheus
        record_llm_request(
            provider="openai",
            model="gpt-4",
            duration_seconds=1.5,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
            success=True
        )

    def test_record_api_request(self):
        """Test recording API request metrics."""
        from src.infrastructure.monitoring.prometheus_metrics import record_api_request

        # Should not raise
        record_api_request(
            service="test_service",
            endpoint="/api/test",
            duration_seconds=0.5,
            success=True,
            rate_limited=False
        )

    def test_record_agent_run(self):
        """Test recording agent run metrics."""
        from src.infrastructure.monitoring.prometheus_metrics import record_agent_run

        # Should not raise
        record_agent_run(
            agent_name="test_agent",
            duration_seconds=10.0,
            success=True,
            steps={"collect": 1, "analyze": 1}
        )

    def test_record_vector_operation(self):
        """Test recording vector operation metrics."""
        from src.infrastructure.monitoring.prometheus_metrics import record_vector_operation

        # Should not raise
        record_vector_operation(
            operation="query",
            namespace="test",
            duration_seconds=0.1,
            success=True,
            results_count=10
        )

    def test_record_cache_operation(self):
        """Test recording cache operation metrics."""
        from src.infrastructure.monitoring.prometheus_metrics import record_cache_operation

        # Should not raise
        record_cache_operation(operation="get", hit=True)
        record_cache_operation(operation="get", hit=False)

    def test_set_gauges(self):
        """Test setting gauge metrics."""
        from src.infrastructure.monitoring.prometheus_metrics import (
            set_active_jobs,
            set_queue_size,
        )

        # Should not raise
        set_active_jobs("http_request", 5)
        set_queue_size("processing", 10)


class TestDecorators:
    """Test metric decorators."""

    def test_track_llm_call_decorator(self):
        """Test track_llm_call decorator."""
        from src.infrastructure.monitoring.prometheus_metrics import track_llm_call

        @track_llm_call(provider="openai", model="gpt-4")
        def mock_llm_call():
            return {"response": "test", "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

        result = mock_llm_call()
        assert result["response"] == "test"

    def test_track_llm_call_with_error(self):
        """Test track_llm_call decorator handles errors."""
        from src.infrastructure.monitoring.prometheus_metrics import track_llm_call

        @track_llm_call(provider="openai", model="gpt-4")
        def failing_llm_call():
            raise ValueError("API Error")

        with pytest.raises(ValueError):
            failing_llm_call()

    def test_track_api_call_decorator(self):
        """Test track_api_call decorator."""
        from src.infrastructure.monitoring.prometheus_metrics import track_api_call

        @track_api_call(service="test", endpoint="/api")
        def mock_api_call():
            return {"status": "ok"}

        result = mock_api_call()
        assert result["status"] == "ok"

    def test_track_agent_run_decorator(self):
        """Test track_agent_run decorator."""
        from src.infrastructure.monitoring.prometheus_metrics import track_agent_run

        @track_agent_run(agent_name="test_agent")
        def mock_agent_run():
            return {"completed": True}

        result = mock_agent_run()
        assert result["completed"] is True


class TestContextManager:
    """Test track_operation context manager."""

    def test_track_operation_success(self):
        """Test tracking successful operation."""
        from src.infrastructure.monitoring.prometheus_metrics import track_operation

        with track_operation("test_op", {"key": "value"}):
            result = 1 + 1

        assert result == 2

    def test_track_operation_failure(self):
        """Test tracking failed operation."""
        from src.infrastructure.monitoring.prometheus_metrics import track_operation

        with pytest.raises(ValueError):
            with track_operation("test_op", {"key": "value"}):
                raise ValueError("Test error")


class TestMetricsExport:
    """Test metrics export functionality."""

    def test_get_metrics(self):
        """Test getting metrics in Prometheus format."""
        from src.infrastructure.monitoring.prometheus_metrics import get_metrics

        metrics = get_metrics()
        assert isinstance(metrics, bytes)

    def test_get_metrics_content_type(self):
        """Test getting metrics content type."""
        from src.infrastructure.monitoring.prometheus_metrics import get_metrics_content_type

        content_type = get_metrics_content_type()
        assert isinstance(content_type, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

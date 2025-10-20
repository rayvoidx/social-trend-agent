"""
Unit tests for retry utilities
"""
import pytest
import time
from agents.shared.retry import (
    backoff_retry,
    retry_on_rate_limit,
    RetryConfig,
    RETRY_CONFIG_DEFAULT
)


class TestBackoffRetry:
    """Tests for backoff_retry decorator"""

    def test_success_on_first_try(self):
        """Test function succeeds on first try"""
        call_count = [0]

        @backoff_retry(max_retries=3)
        def succeed_immediately():
            call_count[0] += 1
            return "success"

        result = succeed_immediately()

        assert result == "success"
        assert call_count[0] == 1  # Called only once

    def test_success_after_retries(self):
        """Test function succeeds after some retries"""
        call_count = [0]

        @backoff_retry(max_retries=5, backoff_factor=0.01)
        def succeed_on_third_try():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = succeed_on_third_try()

        assert result == "success"
        assert call_count[0] == 3  # Called 3 times

    def test_exhausted_retries(self):
        """Test all retries exhausted"""
        @backoff_retry(max_retries=2, backoff_factor=0.01)
        def always_fail():
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            always_fail()

    def test_backoff_timing(self):
        """Test exponential backoff timing"""
        call_times = []

        @backoff_retry(max_retries=3, backoff_base=2.0, backoff_factor=0.1)
        def track_timing():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ConnectionError("Retry")
            return "success"

        track_timing()

        # Check that delays increase exponentially
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]
            # Second delay should be roughly 2x first delay
            assert delay2 > delay1

    def test_custom_exceptions(self):
        """Test catching specific exceptions"""
        @backoff_retry(max_retries=2, exceptions=(ValueError,), backoff_factor=0.01)
        def raise_value_error():
            raise ValueError("Caught")

        @backoff_retry(max_retries=2, exceptions=(ValueError,), backoff_factor=0.01)
        def raise_type_error():
            raise TypeError("Not caught")

        # ValueError should be retried
        with pytest.raises(ValueError):
            raise_value_error()

        # TypeError should not be retried (fail immediately)
        with pytest.raises(TypeError):
            raise_type_error()

    def test_on_retry_callback(self):
        """Test on_retry callback"""
        retry_info = []

        def track_retries(exception, attempt):
            retry_info.append((str(exception), attempt))

        @backoff_retry(max_retries=2, on_retry=track_retries, backoff_factor=0.01)
        def fail_twice():
            if len(retry_info) < 2:
                raise ValueError(f"Attempt {len(retry_info) + 1}")
            return "success"

        result = fail_twice()

        assert result == "success"
        assert len(retry_info) == 2
        assert retry_info[0][1] == 1  # First retry
        assert retry_info[1][1] == 2  # Second retry


class TestRetryOnRateLimit:
    """Tests for retry_on_rate_limit decorator"""

    def test_rate_limit_retry(self):
        """Test retry on rate limit error"""
        import requests

        call_count = [0]

        @retry_on_rate_limit(max_retries=2)
        def api_call_with_rate_limit():
            call_count[0] += 1
            if call_count[0] < 2:
                # Simulate rate limit response
                response = requests.Response()
                response.status_code = 429
                raise requests.exceptions.HTTPError(response=response)
            return "success"

        result = api_call_with_rate_limit()

        assert result == "success"
        assert call_count[0] == 2  # Retried once

    def test_non_rate_limit_error_no_retry(self):
        """Test non-rate-limit errors don't retry"""
        import requests

        @retry_on_rate_limit(max_retries=2)
        def api_call_with_404():
            response = requests.Response()
            response.status_code = 404
            raise requests.exceptions.HTTPError(response=response)

        # Should fail immediately without retry
        with pytest.raises(requests.exceptions.HTTPError):
            api_call_with_404()


class TestRetryConfig:
    """Tests for RetryConfig"""

    def test_default_config(self):
        """Test default retry configuration"""
        config = RETRY_CONFIG_DEFAULT

        assert config.max_retries == 5
        assert config.backoff_base == 2.0
        assert config.backoff_factor == 1.0
        assert config.timeout == 30.0

    def test_custom_config(self):
        """Test custom retry configuration"""
        config = RetryConfig(
            max_retries=10,
            backoff_base=3.0,
            backoff_factor=2.0,
            timeout=60.0
        )

        assert config.max_retries == 10
        assert config.backoff_base == 3.0
        assert config.backoff_factor == 2.0
        assert config.timeout == 60.0


def test_retry_with_args_and_kwargs():
    """Test retry with function arguments"""
    call_log = []

    @backoff_retry(max_retries=2, backoff_factor=0.01)
    def func_with_args(a, b, c=None):
        call_log.append((a, b, c))
        if len(call_log) < 2:
            raise ValueError("Retry")
        return f"{a}-{b}-{c}"

    result = func_with_args("x", "y", c="z")

    assert result == "x-y-z"
    assert len(call_log) == 2
    assert call_log[0] == ("x", "y", "z")
    assert call_log[1] == ("x", "y", "z")

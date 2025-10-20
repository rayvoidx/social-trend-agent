"""
Unit tests for error handling utilities
"""
import pytest
from agents.shared.error_handling import (
    CompletionStatus,
    PartialResult,
    create_full_result,
    create_partial_result,
    create_failed_result,
    safe_api_call
)


class TestCompletionStatus:
    """Tests for CompletionStatus enum"""

    def test_enum_values(self):
        """Test enum values are correct"""
        assert CompletionStatus.FULL.value == "full"
        assert CompletionStatus.PARTIAL.value == "partial"
        assert CompletionStatus.FAILED.value == "failed"


class TestPartialResult:
    """Tests for PartialResult class"""

    def test_initialization(self):
        """Test basic initialization"""
        result = PartialResult(
            status=CompletionStatus.FULL,
            data={"test": "data"}
        )

        assert result.status == CompletionStatus.FULL
        assert result.data == {"test": "data"}
        assert result.successful_operations == []
        assert result.failed_operations == []
        assert result.errors == []
        assert result.warnings == []
        assert result.limitations == []
        assert result.timestamp is not None

    def test_add_warning(self):
        """Test adding warnings"""
        result = PartialResult(status=CompletionStatus.PARTIAL)

        result.add_warning("Warning 1")
        result.add_warning("Warning 2")

        assert len(result.warnings) == 2
        assert "Warning 1" in result.warnings
        assert "Warning 2" in result.warnings

    def test_add_limitation(self):
        """Test adding limitations"""
        result = PartialResult(status=CompletionStatus.PARTIAL)

        result.add_limitation("Limited data source")
        result.add_limitation("No video analysis")

        assert len(result.limitations) == 2
        assert "Limited data source" in result.limitations

    def test_add_error(self):
        """Test adding error details"""
        result = PartialResult(status=CompletionStatus.PARTIAL)

        try:
            raise ValueError("Test error")
        except ValueError as e:
            result.add_error("api_call", e, context={"api": "NewsAPI"})

        assert len(result.errors) == 1
        assert result.errors[0]["operation"] == "api_call"
        assert result.errors[0]["error_type"] == "ValueError"
        assert result.errors[0]["error_message"] == "Test error"
        assert result.errors[0]["context"]["api"] == "NewsAPI"

        assert "api_call" in result.failed_operations

    def test_mark_success(self):
        """Test marking operations as successful"""
        result = PartialResult(status=CompletionStatus.PARTIAL)

        result.mark_success("operation1")
        result.mark_success("operation2")
        result.mark_success("operation1")  # Duplicate

        assert len(result.successful_operations) == 2
        assert "operation1" in result.successful_operations
        assert "operation2" in result.successful_operations

    def test_is_usable_full(self):
        """Test is_usable returns True for FULL status"""
        result = PartialResult(status=CompletionStatus.FULL, data={"test": "data"})
        assert result.is_usable() is True

    def test_is_usable_partial(self):
        """Test is_usable returns True for PARTIAL status"""
        result = PartialResult(status=CompletionStatus.PARTIAL, data={"test": "data"})
        assert result.is_usable() is True

    def test_is_usable_failed(self):
        """Test is_usable returns False for FAILED status"""
        result = PartialResult(status=CompletionStatus.FAILED)
        assert result.is_usable() is False

    def test_to_dict(self):
        """Test serialization to dictionary"""
        result = PartialResult(
            status=CompletionStatus.PARTIAL,
            data={"items": [1, 2, 3]},
            successful_operations=["op1"],
            failed_operations=["op2"],
            warnings=["Warning"],
            limitations=["Limitation"]
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "partial"
        assert result_dict["data"] == {"items": [1, 2, 3]}
        assert result_dict["successful_operations"] == ["op1"]
        assert result_dict["failed_operations"] == ["op2"]
        assert result_dict["warnings"] == ["Warning"]
        assert result_dict["limitations"] == ["Limitation"]
        assert "timestamp" in result_dict

    def test_get_markdown_notice_full(self):
        """Test markdown notice for full completion"""
        result = PartialResult(status=CompletionStatus.FULL, data={"test": "data"})
        notice = result.get_markdown_notice()

        assert notice == ""  # No notice for full success

    def test_get_markdown_notice_partial(self):
        """Test markdown notice for partial completion"""
        result = PartialResult(status=CompletionStatus.PARTIAL)
        result.mark_success("news_api")
        result.add_limitation("YouTube API unavailable")
        result.add_warning("결과가 제한적일 수 있습니다")

        try:
            raise ValueError("API timeout")
        except ValueError as e:
            result.add_error("video_api", e)

        notice = result.get_markdown_notice()

        assert "⚠️" in notice
        assert "부분 완료" in notice
        assert "news_api" in notice
        assert "video_api" in notice
        assert "YouTube API unavailable" in notice
        assert "결과가 제한적일 수 있습니다" in notice

    def test_get_markdown_notice_failed(self):
        """Test markdown notice for failed completion"""
        result = PartialResult(status=CompletionStatus.FAILED)

        try:
            raise ConnectionError("Connection lost")
        except ConnectionError as e:
            result.add_error("critical_api", e)

        notice = result.get_markdown_notice()

        assert "❌" in notice
        assert "작업 실패" in notice
        assert "critical_api" in notice
        assert "ConnectionError" in notice


class TestHelperFunctions:
    """Tests for helper functions"""

    def test_create_full_result(self):
        """Test create_full_result"""
        data = {"items": [1, 2, 3], "count": 3}
        result = create_full_result(data)

        assert result.status == CompletionStatus.FULL
        assert result.data == data
        assert result.is_usable() is True

    def test_create_partial_result(self):
        """Test create_partial_result"""
        data = {"items": [1, 2]}
        successful = ["api1", "api2"]
        failed = ["api3"]
        limitations = ["api3 failed"]

        result = create_partial_result(data, successful, failed, limitations)

        assert result.status == CompletionStatus.PARTIAL
        assert result.data == data
        assert result.successful_operations == successful
        assert result.failed_operations == failed
        assert result.limitations == limitations
        assert result.is_usable() is True

    def test_create_failed_result(self):
        """Test create_failed_result"""
        errors = [
            {
                "operation": "critical_op",
                "error_type": "ValueError",
                "error_message": "Invalid input"
            }
        ]

        result = create_failed_result(errors)

        assert result.status == CompletionStatus.FAILED
        assert result.data is None
        assert result.errors == errors
        assert result.is_usable() is False


class TestSafeApiCall:
    """Tests for safe_api_call wrapper"""

    def test_successful_call(self):
        """Test successful API call"""
        def success_func(x, y):
            return x + y

        result = safe_api_call("add_operation", success_func, 5, 3)

        assert result == 8

    def test_successful_call_with_container(self):
        """Test successful call updates result container"""
        container = PartialResult(status=CompletionStatus.PARTIAL, data={})

        def success_func():
            return "success"

        result = safe_api_call(
            "test_op",
            success_func,
            result_container=container
        )

        assert result == "success"
        assert "test_op" in container.successful_operations
        assert len(container.errors) == 0

    def test_failed_call_with_fallback(self):
        """Test failed call returns fallback value"""
        def failing_func():
            raise ValueError("API error")

        result = safe_api_call(
            "test_op",
            failing_func,
            fallback_value={"default": "value"}
        )

        assert result == {"default": "value"}

    def test_failed_call_updates_container(self):
        """Test failed call updates result container"""
        container = PartialResult(status=CompletionStatus.PARTIAL, data={})

        def failing_func():
            raise ConnectionError("Connection timeout")

        result = safe_api_call(
            "api_call",
            failing_func,
            fallback_value=[],
            result_container=container
        )

        assert result == []
        assert "api_call" in container.failed_operations
        assert len(container.errors) == 1
        assert container.errors[0]["error_type"] == "ConnectionError"
        assert len(container.limitations) == 1

    def test_safe_call_with_args_and_kwargs(self):
        """Test safe_api_call with various arguments"""
        def func_with_args(a, b, c=None):
            if c is None:
                raise ValueError("c is required")
            return a + b + c

        container = PartialResult(status=CompletionStatus.PARTIAL, data={})

        # Successful call
        result1 = safe_api_call(
            "op1",
            func_with_args,
            1, 2,
            c=3,
            result_container=container
        )
        assert result1 == 6

        # Failed call
        result2 = safe_api_call(
            "op2",
            func_with_args,
            1, 2,
            fallback_value=0,
            result_container=container
        )
        assert result2 == 0

        assert "op1" in container.successful_operations
        assert "op2" in container.failed_operations


def test_complex_workflow():
    """Test complex workflow with multiple operations"""
    result = PartialResult(status=CompletionStatus.PARTIAL, data={"results": []})

    # Operation 1: Success
    def fetch_news():
        return [{"title": "News 1"}, {"title": "News 2"}]

    news_data = safe_api_call(
        "fetch_news",
        fetch_news,
        fallback_value=[],
        result_container=result
    )
    result.data["news"] = news_data

    # Operation 2: Failure
    def fetch_videos():
        raise ConnectionError("YouTube API timeout")

    video_data = safe_api_call(
        "fetch_videos",
        fetch_videos,
        fallback_value=[],
        result_container=result
    )
    result.data["videos"] = video_data

    # Operation 3: Success
    def analyze_sentiment():
        return {"positive": 15, "negative": 3}

    sentiment = safe_api_call(
        "analyze_sentiment",
        analyze_sentiment,
        fallback_value={},
        result_container=result
    )
    result.data["sentiment"] = sentiment

    # Verify results
    assert result.data["news"] == [{"title": "News 1"}, {"title": "News 2"}]
    assert result.data["videos"] == []
    assert result.data["sentiment"]["positive"] == 15

    assert "fetch_news" in result.successful_operations
    assert "fetch_videos" in result.failed_operations
    assert "analyze_sentiment" in result.successful_operations

    assert len(result.errors) == 1
    assert result.errors[0]["operation"] == "fetch_videos"

    # Test markdown notice
    notice = result.get_markdown_notice()
    assert "fetch_news" in notice
    assert "fetch_videos" in notice
    assert "analyze_sentiment" in notice

"""
Error handling utilities for graceful degradation
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class CompletionStatus(Enum):
    """Completion status for agent operations"""
    FULL = "full"
    PARTIAL = "partial"
    FAILED = "failed"


class PartialResult:
    """
    Container for partial results with metadata about what succeeded/failed
    """

    def __init__(
        self,
        status: CompletionStatus,
        data: Any = None,
        successful_operations: Optional[List[str]] = None,
        failed_operations: Optional[List[str]] = None,
        errors: Optional[List[Dict[str, Any]]] = None,
        warnings: Optional[List[str]] = None,
        limitations: Optional[List[str]] = None
    ):
        """
        Args:
            status: Overall completion status
            data: The actual result data (may be incomplete)
            successful_operations: List of operations that succeeded
            failed_operations: List of operations that failed
            errors: List of error details
            warnings: List of warnings to include in report
            limitations: List of limitations to disclose
        """
        self.status = status
        self.data = data
        self.successful_operations = successful_operations or []
        self.failed_operations = failed_operations or []
        self.errors = errors or []
        self.warnings = warnings or []
        self.limitations = limitations or []
        self.timestamp = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "status": self.status.value,
            "data": self.data,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "errors": self.errors,
            "warnings": self.warnings,
            "limitations": self.limitations,
            "timestamp": self.timestamp
        }

    def add_warning(self, warning: str):
        """Add a warning message"""
        self.warnings.append(warning)

    def add_limitation(self, limitation: str):
        """Add a limitation note"""
        self.limitations.append(limitation)

    def add_error(self, operation: str, error: Exception, context: Optional[Dict] = None):
        """
        Add error details

        Args:
            operation: Name of the failed operation
            error: The exception that occurred
            context: Additional context (e.g., API endpoint, query)
        """
        error_detail = {
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {}
        }
        self.errors.append(error_detail)

        if operation not in self.failed_operations:
            self.failed_operations.append(operation)

    def mark_success(self, operation: str):
        """Mark an operation as successful"""
        if operation not in self.successful_operations:
            self.successful_operations.append(operation)

    def is_usable(self) -> bool:
        """Check if result is usable despite being partial"""
        return self.status in (CompletionStatus.FULL, CompletionStatus.PARTIAL)

    def get_markdown_notice(self) -> str:
        """
        Generate markdown notice for reports

        Returns:
            Markdown formatted notice about partial completion
        """
        if self.status == CompletionStatus.FULL:
            return ""

        lines = []

        if self.status == CompletionStatus.PARTIAL:
            lines.append("⚠️ **부분 완료 알림 (Partial Completion Notice)**\n")
            lines.append("일부 데이터 수집/분석 작업이 실패했습니다. 아래 결과는 제한적일 수 있습니다.\n")

        elif self.status == CompletionStatus.FAILED:
            lines.append("❌ **작업 실패 알림 (Operation Failed)**\n")
            lines.append("주요 작업이 실패했습니다. 결과를 신뢰하지 마세요.\n")

        if self.successful_operations:
            lines.append(f"✅ **성공한 작업**: {', '.join(self.successful_operations)}\n")

        if self.failed_operations:
            lines.append(f"❌ **실패한 작업**: {', '.join(self.failed_operations)}\n")

        if self.limitations:
            lines.append("\n**제한사항 (Limitations)**:\n")
            for limitation in self.limitations:
                lines.append(f"- {limitation}\n")

        if self.warnings:
            lines.append("\n**경고 (Warnings)**:\n")
            for warning in self.warnings:
                lines.append(f"- {warning}\n")

        if self.errors:
            lines.append("\n**오류 상세 (Error Details)**:\n")
            for error in self.errors:
                lines.append(f"- **{error['operation']}**: {error['error_type']} - {error['error_message']}\n")

        lines.append("\n---\n")

        return "".join(lines)


def create_full_result(data: Any) -> PartialResult:
    """
    Create a fully successful result

    Args:
        data: The complete result data

    Returns:
        PartialResult with FULL status
    """
    return PartialResult(status=CompletionStatus.FULL, data=data)


def create_partial_result(
    data: Any,
    successful_ops: List[str],
    failed_ops: List[str],
    limitations: Optional[List[str]] = None
) -> PartialResult:
    """
    Create a partial result

    Args:
        data: The partial result data
        successful_ops: Operations that succeeded
        failed_ops: Operations that failed
        limitations: Optional limitations to note

    Returns:
        PartialResult with PARTIAL status
    """
    result = PartialResult(
        status=CompletionStatus.PARTIAL,
        data=data,
        successful_operations=successful_ops,
        failed_operations=failed_ops,
        limitations=limitations
    )
    return result


def create_failed_result(errors: List[Dict[str, Any]]) -> PartialResult:
    """
    Create a failed result

    Args:
        errors: List of error details

    Returns:
        PartialResult with FAILED status
    """
    return PartialResult(
        status=CompletionStatus.FAILED,
        data=None,
        errors=errors
    )


def safe_api_call(
    operation_name: str,
    api_func,
    *args,
    fallback_value=None,
    result_container: Optional[PartialResult] = None,
    **kwargs
):
    """
    Safely execute an API call with error handling

    Args:
        operation_name: Name of the operation (for logging)
        api_func: Function to call
        *args: Positional arguments for api_func
        fallback_value: Value to return on failure
        result_container: Optional PartialResult to update
        **kwargs: Keyword arguments for api_func

    Returns:
        Result from api_func or fallback_value on error
    """
    try:
        result = api_func(*args, **kwargs)
        if result_container:
            result_container.mark_success(operation_name)
        return result

    except Exception as e:
        if result_container:
            result_container.add_error(operation_name, e, context={
                "args": str(args)[:100],  # Truncate long args
                "kwargs": str(kwargs)[:100]
            })
            result_container.add_limitation(
                f"{operation_name} 실패로 인해 데이터가 불완전할 수 있습니다."
            )

        return fallback_value


# Example usage:
if __name__ == "__main__":
    import requests

    # Example 1: Full success
    result = create_full_result({"data": [1, 2, 3]})
    print("Full result status:", result.status.value)
    print(result.get_markdown_notice())  # Empty for full success

    # Example 2: Partial completion
    partial_result = PartialResult(status=CompletionStatus.PARTIAL)
    partial_result.mark_success("news_api")
    partial_result.mark_success("sentiment_analysis")

    try:
        # Simulate API failure
        raise requests.exceptions.Timeout("API timeout after 30s")
    except Exception as e:
        partial_result.add_error("video_api", e, context={"platform": "youtube"})

    partial_result.add_limitation("YouTube API 타임아웃으로 비디오 분석 제외")
    partial_result.add_warning("결과는 뉴스 데이터만 포함합니다")

    print("\nPartial result notice:")
    print(partial_result.get_markdown_notice())

    # Example 3: Using safe_api_call
    result_container = PartialResult(status=CompletionStatus.PARTIAL, data={})

    def flaky_api():
        raise ConnectionError("Connection failed")

    data = safe_api_call(
        "external_api",
        flaky_api,
        fallback_value={"items": []},
        result_container=result_container
    )

    print("\nSafe API call result:", data)
    print("Errors:", result_container.errors)

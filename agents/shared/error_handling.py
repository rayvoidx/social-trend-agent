"""
우아한 실패 처리를 위한 에러 핸들링 유틸리티
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class CompletionStatus(Enum):
    """에이전트 작업의 완료 상태"""
    FULL = "full"
    PARTIAL = "partial"
    FAILED = "failed"


class PartialResult:
    """
    부분 결과 컨테이너

    성공/실패한 작업에 대한 메타데이터를 포함합니다.
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
            status: 전체 완료 상태
            data: 실제 결과 데이터 (불완전할 수 있음)
            successful_operations: 성공한 작업 목록
            failed_operations: 실패한 작업 목록
            errors: 에러 상세 정보 목록
            warnings: 리포트에 포함할 경고 목록
            limitations: 공개할 제한사항 목록
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
        """직렬화를 위해 딕셔너리로 변환"""
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
        """경고 메시지 추가"""
        self.warnings.append(warning)

    def add_limitation(self, limitation: str):
        """제한사항 노트 추가"""
        self.limitations.append(limitation)

    def add_error(self, operation: str, error: Exception, context: Optional[Dict] = None):
        """
        에러 상세 정보 추가

        Args:
            operation: 실패한 작업명
            error: 발생한 예외
            context: 추가 컨텍스트 (예: API 엔드포인트, 쿼리)
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
        """작업을 성공으로 표시"""
        if operation not in self.successful_operations:
            self.successful_operations.append(operation)

    def is_usable(self) -> bool:
        """부분 완료 상태임에도 결과가 사용 가능한지 확인"""
        return self.status in (CompletionStatus.FULL, CompletionStatus.PARTIAL)

    def get_markdown_notice(self) -> str:
        """
        리포트용 마크다운 노티스 생성

        Returns:
            부분 완료에 대한 마크다운 형식의 알림
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
    완전히 성공한 결과 생성

    Args:
        data: 완전한 결과 데이터

    Returns:
        FULL 상태의 PartialResult
    """
    return PartialResult(status=CompletionStatus.FULL, data=data)


def create_partial_result(
    data: Any,
    successful_ops: List[str],
    failed_ops: List[str],
    limitations: Optional[List[str]] = None
) -> PartialResult:
    """
    부분 결과 생성

    Args:
        data: 부분 결과 데이터
        successful_ops: 성공한 작업들
        failed_ops: 실패한 작업들
        limitations: 선택적 제한사항

    Returns:
        PARTIAL 상태의 PartialResult
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
    실패한 결과 생성

    Args:
        errors: 에러 상세 정보 리스트

    Returns:
        FAILED 상태의 PartialResult
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
    에러 핸들링을 통한 안전한 API 호출

    Args:
        operation_name: 작업명 (로깅용)
        api_func: 호출할 함수
        *args: api_func의 위치 인자
        fallback_value: 실패 시 반환할 값
        result_container: 업데이트할 선택적 PartialResult
        **kwargs: api_func의 키워드 인자

    Returns:
        api_func의 결과 또는 에러 시 fallback_value
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


# 사용 예제:
if __name__ == "__main__":
    import requests

    # 예제 1: 완전 성공
    result = create_full_result({"data": [1, 2, 3]})
    print("Full result status:", result.status.value)
    print(result.get_markdown_notice())  # 완전 성공 시 빈 문자열

    # 예제 2: 부분 완료
    partial_result = PartialResult(status=CompletionStatus.PARTIAL)
    partial_result.mark_success("news_api")
    partial_result.mark_success("sentiment_analysis")

    try:
        # API 실패 시뮬레이션
        raise requests.exceptions.Timeout("API timeout after 30s")
    except Exception as e:
        partial_result.add_error("video_api", e, context={"platform": "youtube"})

    partial_result.add_limitation("YouTube API 타임아웃으로 비디오 분석 제외")
    partial_result.add_warning("결과는 뉴스 데이터만 포함합니다")

    print("\nPartial result notice:")
    print(partial_result.get_markdown_notice())

    # 예제 3: safe_api_call 사용
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

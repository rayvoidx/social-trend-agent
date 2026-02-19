"""
에이전트를 위한 구조화된 JSON 로깅
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


class JsonLineFormatter(logging.Formatter):
    """
    손쉬운 파싱을 위한 JSON 라인 형식 포매터
    """

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 JSON 라인으로 포매팅"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 추가 필드 포함
        if hasattr(record, "run_id"):
            log_data["run_id"] = record.run_id

        if hasattr(record, "agent"):
            log_data["agent"] = record.agent

        if hasattr(record, "node"):
            log_data["node"] = record.node

        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        # 예외 정보가 있으면 추가
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 커스텀 필드 추가
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "run_id",
                "agent",
                "node",
                "duration_ms",
            ]:
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(
    level: int = logging.INFO, log_file: Optional[str] = None, json_format: bool = True
) -> logging.Logger:
    """
    구조화된 로깅 설정

    Args:
        level: 로깅 레벨 (기본값: INFO)
        log_file: 선택적 로그 파일 경로
        json_format: JSON 라인 형식 사용 (기본값: True)

    Returns:
        루트 로거
    """
    logger = logging.getLogger()
    logger.setLevel(level)

    # 기존 핸들러 제거
    logger.handlers.clear()

    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if json_format:
        console_handler.setFormatter(JsonLineFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

    logger.addHandler(console_handler)

    # 파일 핸들러 설정 (지정된 경우)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)

        if json_format:
            file_handler.setFormatter(JsonLineFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            )

        logger.addHandler(file_handler)

    return logger


class AgentLogger:
    """
    run_id 추적 기능을 갖춘 에이전트용 구조화된 로거

    각 실행(run)마다 고유 ID를 부여하여 분산 환경에서도
    로그를 추적하고 디버깅할 수 있도록 지원합니다.
    """

    def __init__(self, agent_name: str, run_id: str):
        """
        Args:
            agent_name: 에이전트 이름
            run_id: 고유 실행 식별자
        """
        self.agent_name = agent_name
        self.run_id = run_id
        self.logger = logging.getLogger(f"agent.{agent_name}")

    def _log(self, level: int, message: str, **extra):
        """추가 필드와 함께 로그를 기록하는 내부 메서드"""
        # exc_info, stack_info, stacklevel are reserved Logger.log() kwargs
        # — extract them from extra so they don't collide with LogRecord fields
        exc_info = extra.pop("exc_info", None)
        stack_info = extra.pop("stack_info", False)
        stacklevel = extra.pop("stacklevel", 1)
        extra["run_id"] = self.run_id
        extra["agent"] = self.agent_name
        self.logger.log(
            level, message, exc_info=exc_info, stack_info=stack_info,
            stacklevel=stacklevel, extra=extra,
        )

    def debug(self, message: str, **extra):
        """디버그 메시지 로깅"""
        self._log(logging.DEBUG, message, **extra)

    def info(self, message: str, **extra):
        """정보 메시지 로깅"""
        self._log(logging.INFO, message, **extra)

    def warning(self, message: str, **extra):
        """경고 메시지 로깅"""
        self._log(logging.WARNING, message, **extra)

    def error(self, message: str, **extra):
        """에러 메시지 로깅"""
        self._log(logging.ERROR, message, **extra)

    def node_start(self, node_name: str, input_size: int = 0, **kwargs):
        """노드 시작 로깅"""
        self.info(
            f"Node started: {node_name}",
            node=node_name,
            event="node_start",
            input_size=input_size,
            **kwargs,
        )

    def node_end(self, node_name: str, output_size: int = 0, duration_ms: int = 0, **kwargs):
        """노드 완료 로깅"""
        self.info(
            f"Node completed: {node_name}",
            node=node_name,
            event="node_end",
            output_size=output_size,
            duration_ms=duration_ms,
            **kwargs,
        )

    def node_error(self, node_name: str, error: Exception):
        """노드 에러 로깅"""
        self.error(
            f"Node failed: {node_name}",
            node=node_name,
            event="node_error",
            error_type=type(error).__name__,
            error_message=str(error),
        )


def log_json_line(data: Dict[str, Any], logger: Optional[logging.Logger] = None):
    """
    JSON 라인을 직접 로깅

    Args:
        data: JSON으로 로깅할 딕셔너리
        logger: 선택적 로거 (제공하지 않으면 루트 로거 사용)
    """
    if logger is None:
        logger = logging.getLogger()

    # 타임스탬프 보장
    if "timestamp" not in data:
        data["timestamp"] = datetime.utcnow().isoformat() + "Z"

    # JSON 문자열로 로깅
    logger.info(json.dumps(data, ensure_ascii=False))


# 사용 예시:
if __name__ == "__main__":
    import time

    # JSON 로깅 설정
    setup_logging(level=logging.DEBUG, json_format=True)

    # 에이전트 로거 생성
    agent_logger = AgentLogger("news_trend_agent", "test-run-123")

    # 노드 실행 로깅
    agent_logger.node_start("collect", input_size=0)
    time.sleep(0.1)
    agent_logger.info("Collecting news from API", api="NewsAPI", query="test")
    time.sleep(0.1)
    agent_logger.node_end("collect", output_size=15, duration_ms=200)

    # 에러 로깅
    try:
        raise ValueError("Test error")
    except Exception as e:
        agent_logger.node_error("analyze", e)

    # JSON 라인 직접 로깅
    log_json_line(
        {
            "run_id": "test-run-123",
            "agent": "news_trend_agent",
            "event": "complete",
            "total_duration_ms": 5000,
            "metrics": {"coverage": 0.9, "factuality": 1.0},
        }
    )

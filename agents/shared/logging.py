"""
Structured JSON logging for agents
"""
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


class JsonLineFormatter(logging.Formatter):
    """
    Formatter that outputs JSON lines for easy parsing
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON line"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "run_id"):
            log_data["run_id"] = record.run_id

        if hasattr(record, "agent"):
            log_data["agent"] = record.agent

        if hasattr(record, "node"):
            log_data["node"] = record.node

        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any custom extra fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "created", "filename", "funcName",
                          "levelname", "levelno", "lineno", "module", "msecs",
                          "message", "pathname", "process", "processName",
                          "relativeCreated", "thread", "threadName", "exc_info",
                          "exc_text", "stack_info", "run_id", "agent", "node",
                          "duration_ms"]:
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    json_format: bool = True
) -> logging.Logger:
    """
    Setup structured logging

    Args:
        level: Logging level (default: INFO)
        log_file: Optional log file path
        json_format: Use JSON line format (default: True)

    Returns:
        Root logger
    """
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if json_format:
        console_handler.setFormatter(JsonLineFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)

        if json_format:
            file_handler.setFormatter(JsonLineFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )

        logger.addHandler(file_handler)

    return logger


class AgentLogger:
    """
    Structured logger for agents with run_id tracking
    """

    def __init__(self, agent_name: str, run_id: str):
        """
        Args:
            agent_name: Name of the agent
            run_id: Unique run identifier
        """
        self.agent_name = agent_name
        self.run_id = run_id
        self.logger = logging.getLogger(f"agent.{agent_name}")

    def _log(self, level: int, message: str, **extra):
        """Internal log method with extra fields"""
        extra["run_id"] = self.run_id
        extra["agent"] = self.agent_name
        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, **extra):
        """Log debug message"""
        self._log(logging.DEBUG, message, **extra)

    def info(self, message: str, **extra):
        """Log info message"""
        self._log(logging.INFO, message, **extra)

    def warning(self, message: str, **extra):
        """Log warning message"""
        self._log(logging.WARNING, message, **extra)

    def error(self, message: str, **extra):
        """Log error message"""
        self._log(logging.ERROR, message, **extra)

    def node_start(self, node_name: str, input_size: int = 0):
        """Log node start"""
        self.info(
            f"Node started: {node_name}",
            node=node_name,
            event="node_start",
            input_size=input_size
        )

    def node_end(self, node_name: str, output_size: int = 0, duration_ms: int = 0):
        """Log node end"""
        self.info(
            f"Node completed: {node_name}",
            node=node_name,
            event="node_end",
            output_size=output_size,
            duration_ms=duration_ms
        )

    def node_error(self, node_name: str, error: Exception):
        """Log node error"""
        self.error(
            f"Node failed: {node_name}",
            node=node_name,
            event="node_error",
            error_type=type(error).__name__,
            error_message=str(error)
        )


def log_json_line(data: Dict[str, Any], logger: Optional[logging.Logger] = None):
    """
    Log a JSON line directly

    Args:
        data: Dictionary to log as JSON
        logger: Optional logger (uses root logger if not provided)
    """
    if logger is None:
        logger = logging.getLogger()

    # Ensure timestamp
    if "timestamp" not in data:
        data["timestamp"] = datetime.utcnow().isoformat() + "Z"

    # Log as JSON string
    logger.info(json.dumps(data, ensure_ascii=False))


# Example usage:
if __name__ == "__main__":
    import time

    # Setup JSON logging
    setup_logging(level=logging.DEBUG, json_format=True)

    # Create agent logger
    agent_logger = AgentLogger("news_trend_agent", "test-run-123")

    # Log node execution
    agent_logger.node_start("collect", input_size=0)
    time.sleep(0.1)
    agent_logger.info("Collecting news from API", api="NewsAPI", query="test")
    time.sleep(0.1)
    agent_logger.node_end("collect", output_size=15, duration_ms=200)

    # Log error
    try:
        raise ValueError("Test error")
    except Exception as e:
        agent_logger.node_error("analyze", e)

    # Direct JSON line logging
    log_json_line({
        "run_id": "test-run-123",
        "agent": "news_trend_agent",
        "event": "complete",
        "total_duration_ms": 5000,
        "metrics": {
            "coverage": 0.9,
            "factuality": 1.0
        }
    })

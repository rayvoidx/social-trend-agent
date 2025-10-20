"""
Unit tests for logging utilities
"""
import pytest
import logging
import json
import tempfile
from pathlib import Path
from agents.shared.logging import (
    JsonLineFormatter,
    setup_logging,
    AgentLogger,
    log_json_line
)


class TestJsonLineFormatter:
    """Tests for JsonLineFormatter"""

    def test_basic_formatting(self):
        """Test basic JSON line formatting"""
        formatter = JsonLineFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_extra_fields(self):
        """Test extra fields are included"""
        formatter = JsonLineFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.run_id = "test-run-123"
        record.agent = "news_trend_agent"
        record.node = "collect"
        record.duration_ms = 250

        result = formatter.format(record)
        data = json.loads(result)

        assert data["run_id"] == "test-run-123"
        assert data["agent"] == "news_trend_agent"
        assert data["node"] == "collect"
        assert data["duration_ms"] == 250

    def test_exception_formatting(self):
        """Test exception info is formatted"""
        formatter = JsonLineFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=exc_info
            )

            result = formatter.format(record)
            data = json.loads(result)

            assert data["level"] == "ERROR"
            assert "exception" in data
            assert "ValueError" in data["exception"]
            assert "Test error" in data["exception"]

    def test_custom_fields(self):
        """Test custom extra fields are included"""
        formatter = JsonLineFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Custom fields test",
            args=(),
            exc_info=None
        )
        record.custom_field = "custom_value"
        record.api_call = "NewsAPI"

        result = formatter.format(record)
        data = json.loads(result)

        assert data["custom_field"] == "custom_value"
        assert data["api_call"] == "NewsAPI"


class TestSetupLogging:
    """Tests for setup_logging"""

    def test_basic_setup(self):
        """Test basic logging setup"""
        logger = setup_logging(level=logging.DEBUG, json_format=True)

        assert logger is not None
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) > 0

        # Check handler has JsonLineFormatter
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, JsonLineFormatter)

    def test_non_json_format(self):
        """Test setup with standard formatting"""
        logger = setup_logging(level=logging.INFO, json_format=False)

        handler = logger.handlers[0]
        assert not isinstance(handler.formatter, JsonLineFormatter)
        assert isinstance(handler.formatter, logging.Formatter)

    def test_file_logging(self):
        """Test logging to file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            logger = setup_logging(
                level=logging.INFO,
                log_file=str(log_file),
                json_format=True
            )

            # Write a log message
            logger.info("Test message")

            # Check file exists and contains log
            assert log_file.exists()
            content = log_file.read_text()
            assert "Test message" in content

            # Verify JSON format
            data = json.loads(content.strip())
            assert data["message"] == "Test message"


class TestAgentLogger:
    """Tests for AgentLogger"""

    def setup_method(self):
        """Setup test logger"""
        setup_logging(level=logging.DEBUG, json_format=True)

    def test_initialization(self):
        """Test AgentLogger initialization"""
        logger = AgentLogger("test_agent", "run-123")

        assert logger.agent_name == "test_agent"
        assert logger.run_id == "run-123"

    def test_debug_logging(self):
        """Test debug level logging"""
        logger = AgentLogger("test_agent", "run-123")

        # Should not raise error
        logger.debug("Debug message", extra_field="value")

    def test_info_logging(self):
        """Test info level logging"""
        logger = AgentLogger("test_agent", "run-123")
        logger.info("Info message", api="NewsAPI")

    def test_warning_logging(self):
        """Test warning level logging"""
        logger = AgentLogger("test_agent", "run-123")
        logger.warning("Warning message")

    def test_error_logging(self):
        """Test error level logging"""
        logger = AgentLogger("test_agent", "run-123")
        logger.error("Error message", error_code=500)

    def test_node_start(self):
        """Test node_start logging"""
        logger = AgentLogger("test_agent", "run-123")
        logger.node_start("collect", input_size=0)

    def test_node_end(self):
        """Test node_end logging"""
        logger = AgentLogger("test_agent", "run-123")
        logger.node_end("collect", output_size=15, duration_ms=250)

    def test_node_error(self):
        """Test node_error logging"""
        logger = AgentLogger("test_agent", "run-123")

        try:
            raise ValueError("Test node error")
        except ValueError as e:
            logger.node_error("analyze", e)

    def test_extra_fields_propagation(self):
        """Test extra fields are properly propagated"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            setup_logging(
                level=logging.INFO,
                log_file=str(log_file),
                json_format=True
            )

            logger = AgentLogger("test_agent", "run-123")
            logger.info("Test message", custom_field="custom_value")

            # Read log file
            content = log_file.read_text()
            data = json.loads(content.strip())

            assert data["run_id"] == "run-123"
            assert data["agent"] == "test_agent"
            assert data["message"] == "Test message"
            assert data["custom_field"] == "custom_value"


class TestLogJsonLine:
    """Tests for log_json_line utility"""

    def test_basic_json_logging(self):
        """Test logging JSON data directly"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            logger = setup_logging(
                level=logging.INFO,
                log_file=str(log_file),
                json_format=True
            )

            data = {
                "run_id": "test-123",
                "agent": "news_trend_agent",
                "event": "complete",
                "metrics": {"coverage": 0.9}
            }

            log_json_line(data, logger=logger)

            # Read and verify
            content = log_file.read_text()
            assert "test-123" in content
            assert "news_trend_agent" in content

    def test_timestamp_auto_added(self):
        """Test timestamp is automatically added"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            logger = setup_logging(
                level=logging.INFO,
                log_file=str(log_file),
                json_format=True
            )

            data = {"event": "test"}
            log_json_line(data, logger=logger)

            content = log_file.read_text()
            assert "timestamp" in content

    def test_complex_data(self):
        """Test logging complex nested data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            logger = setup_logging(
                level=logging.INFO,
                log_file=str(log_file),
                json_format=True
            )

            data = {
                "run_id": "test-123",
                "metrics": {
                    "coverage": 0.9,
                    "factuality": 1.0
                },
                "keywords": ["키워드1", "키워드2"],
                "sentiment": {
                    "positive": 15,
                    "neutral": 5,
                    "negative": 2
                }
            }

            log_json_line(data, logger=logger)

            # Read and parse
            content = log_file.read_text()
            assert "키워드1" in content
            assert "0.9" in content


def test_unicode_logging():
    """Test logging with Unicode characters"""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file = Path(temp_dir) / "test.log"

        logger = setup_logging(
            level=logging.INFO,
            log_file=str(log_file),
            json_format=True
        )

        agent_logger = AgentLogger("테스트_에이전트", "run-123")
        agent_logger.info("한글 메시지 테스트", 키워드="값")

        # Read log file
        content = log_file.read_text(encoding="utf-8")
        assert "한글 메시지 테스트" in content


def test_log_level_filtering():
    """Test log level filtering works correctly"""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file = Path(temp_dir) / "test.log"

        # Setup with INFO level
        logger = setup_logging(
            level=logging.INFO,
            log_file=str(log_file),
            json_format=True
        )

        agent_logger = AgentLogger("test_agent", "run-123")

        # Debug should be filtered out
        agent_logger.debug("Debug message")

        # Info should be logged
        agent_logger.info("Info message")

        # Read log file
        content = log_file.read_text()

        assert "Debug message" not in content
        assert "Info message" in content

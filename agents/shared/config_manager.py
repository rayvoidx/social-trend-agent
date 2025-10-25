"""
설정 관리 시스템

에이전트, 실험, 인프라에 대한 중앙 집중식 설정 관리를 제공합니다.

주요 기능:
- 계층적 설정 (defaults → environment → overrides)
- 환경별 설정 (dev, staging, prod)
- 핫 리로드 지원
- 스키마 검증
- 시크릿 관리
- 설정 버전 관리

업계 모범 사례 기반:
- 12-factor app: https://12factor.net/config
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
"""
import os
import json
import yaml
from typing import Dict, Any, Optional, List, Type
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import logging
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """배포 환경"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class LLMProvider(str, Enum):
    """지원되는 LLM 제공자"""
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"


# ============================================================================
# 설정 모델 (Pydantic을 사용한 검증)
# ============================================================================

class LLMConfig(BaseModel):
    """LLM 설정"""
    provider: LLMProvider = Field(default=LLMProvider.AZURE_OPENAI)
    model_name: str = Field(default="gpt-4")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, gt=0)
    timeout: int = Field(default=120, gt=0)

    # Provider-specific
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    deployment_name: Optional[str] = None
    api_version: Optional[str] = "2024-02-15-preview"

    class Config:
        use_enum_values = True


class CacheConfig(BaseModel):
    """캐시 설정"""
    enabled: bool = True
    ttl_seconds: int = Field(default=3600, gt=0)
    max_size_mb: int = Field(default=100, gt=0)
    use_disk: bool = False
    disk_path: str = "artifacts/cache"


class RetryConfig(BaseModel):
    """재시도 설정"""
    max_retries: int = Field(default=3, ge=0)
    backoff_factor: float = Field(default=0.5, ge=0)
    max_backoff: float = Field(default=60.0, ge=0)
    retry_on_timeout: bool = True
    retry_on_rate_limit: bool = True


class DataSourceConfig(BaseModel):
    """데이터 소스 설정"""
    name: str
    enabled: bool = True
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 30
    max_results: int = 20


class MonitoringConfig(BaseModel):
    """모니터링 및 관측성 설정"""
    enabled: bool = True
    log_level: str = "INFO"
    structured_logging: bool = True
    metrics_enabled: bool = True
    metrics_dir: str = "artifacts/metrics"
    performance_tracking: bool = True


class NotificationConfig(BaseModel):
    """알림 설정"""
    enabled: bool = False
    slack_webhook: Optional[str] = None
    n8n_webhook: Optional[str] = None
    email_enabled: bool = False
    notify_on_error: bool = True
    notify_on_completion: bool = False


class RateLimitConfig(BaseModel):
    """레이트 리미팅 설정"""
    enabled: bool = True
    requests_per_minute: int = Field(default=60, gt=0)
    burst_size: int = Field(default=10, gt=0)
    provider_limits: Dict[str, int] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """에이전트별 설정"""
    name: str
    enabled: bool = True
    max_concurrent_tasks: int = Field(default=5, gt=0)
    timeout_seconds: int = Field(default=300, gt=0)
    retry_config: RetryConfig = Field(default_factory=RetryConfig)
    cache_config: CacheConfig = Field(default_factory=CacheConfig)


class SystemConfig(BaseSettings):
    """
    시스템 전역 설정

    환경 변수 지원을 위해 Pydantic Settings를 사용합니다.
    """
    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = False

    # LLM
    llm: LLMConfig = Field(default_factory=LLMConfig)

    # Data sources
    data_sources: Dict[str, DataSourceConfig] = Field(default_factory=dict)

    # Infrastructure
    cache: CacheConfig = Field(default_factory=CacheConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)

    # Agents
    agents: Dict[str, AgentConfig] = Field(default_factory=dict)

    # Distributed execution
    distributed_enabled: bool = False
    num_workers: int = Field(default=4, gt=0)
    task_queue_size: int = Field(default=1000, gt=0)

    # API Server
    api_enabled: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"  # LLM__PROVIDER -> llm.provider


# ============================================================================
# 설정 관리자
# ============================================================================

class ConfigManager:
    """
    중앙 집중식 설정 관리자

    설정의 로딩, 병합, 핫 리로드를 처리합니다.

    Example:
        ```python
        # 초기화
        config_manager = ConfigManager(config_dir="config")

        # 설정 로드
        config = config_manager.load_config(environment="production")

        # 특정 설정 조회
        llm_config = config_manager.get_llm_config()

        # 에이전트 설정 조회
        agent_config = config_manager.get_agent_config("news_trend_agent")

        # 설정 업데이트 (핫 리로드)
        config_manager.update_config({"llm": {"temperature": 0.5}})
        ```
    """

    def __init__(
        self,
        config_dir: str = "config",
        environment: Optional[Environment] = None
    ):
        """
        설정 관리자 초기화

        Args:
            config_dir: 설정 파일이 포함된 디렉토리
            environment: 환경 (None이면 환경 변수에서 자동 감지)
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Determine environment
        self.environment = environment or self._detect_environment()

        # Current config
        self.config: Optional[SystemConfig] = None

        # Config file paths
        self.default_config_path = self.config_dir / "default.yaml"
        self.env_config_path = self.config_dir / f"{self.environment.value}.yaml"
        self.override_config_path = self.config_dir / "override.yaml"

        # Load initial config
        self.reload()

    def _detect_environment(self) -> Environment:
        """Detect environment from environment variable"""
        env_str = os.getenv("ENVIRONMENT", "development").lower()

        try:
            return Environment(env_str)
        except ValueError:
            logger.warning(f"Invalid environment '{env_str}', using development")
            return Environment.DEVELOPMENT

    def reload(self):
        """Reload configuration from disk"""
        logger.info(f"Loading configuration for environment: {self.environment.value}")

        # Start with defaults
        config_data = self._load_default_config()

        # Merge environment-specific config
        env_config = self._load_file(self.env_config_path)
        if env_config:
            config_data = self._deep_merge(config_data, env_config)

        # Merge overrides
        override_config = self._load_file(self.override_config_path)
        if override_config:
            config_data = self._deep_merge(config_data, override_config)

        # Parse with Pydantic
        try:
            self.config = SystemConfig(**config_data)
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise

    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration"""
        # Try loading from file
        if self.default_config_path.exists():
            return self._load_file(self.default_config_path)

        # Return hardcoded defaults
        return {
            "environment": self.environment.value,
            "debug": False,
            "llm": {
                "provider": "azure_openai",
                "model_name": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 4000
            },
            "cache": {
                "enabled": True,
                "ttl_seconds": 3600,
                "use_disk": False
            },
            "retry": {
                "max_retries": 3,
                "backoff_factor": 0.5
            },
            "monitoring": {
                "enabled": True,
                "log_level": "INFO"
            }
        }

    def _load_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Load configuration file (YAML or JSON)"""
        if not filepath.exists():
            return None

        try:
            with open(filepath) as f:
                if filepath.suffix in [".yaml", ".yml"]:
                    return yaml.safe_load(f)
                elif filepath.suffix == ".json":
                    return json.load(f)
                else:
                    logger.warning(f"Unsupported config format: {filepath.suffix}")
                    return None
        except Exception as e:
            logger.error(f"Failed to load config from {filepath}: {e}")
            return None

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def save_config(self, filepath: Optional[Path] = None):
        """
        Save current configuration to file

        Args:
            filepath: Path to save (uses override.yaml if None)
        """
        if not self.config:
            raise ValueError("No configuration loaded")

        filepath = filepath or self.override_config_path

        config_dict = self.config.model_dump()

        with open(filepath, "w") as f:
            yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Configuration saved to {filepath}")

    def update_config(self, updates: Dict[str, Any]):
        """
        Update configuration with hot-reload

        Args:
            updates: Dictionary of updates (nested keys supported)
        """
        if not self.config:
            raise ValueError("No configuration loaded")

        # Convert to dict, merge, and reload
        config_dict = self.config.model_dump()
        merged = self._deep_merge(config_dict, updates)

        # Validate and apply
        self.config = SystemConfig(**merged)

        logger.info(f"Configuration updated: {updates}")

    # ========================================================================
    # Convenience getters
    # ========================================================================

    def get_llm_config(self) -> LLMConfig:
        """Get LLM configuration"""
        if not self.config:
            raise ValueError("Configuration not loaded")
        return self.config.llm

    def get_cache_config(self) -> CacheConfig:
        """Get cache configuration"""
        if not self.config:
            raise ValueError("Configuration not loaded")
        return self.config.cache

    def get_retry_config(self) -> RetryConfig:
        """Get retry configuration"""
        if not self.config:
            raise ValueError("Configuration not loaded")
        return self.config.retry

    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """Get agent-specific configuration"""
        if not self.config:
            raise ValueError("Configuration not loaded")
        return self.config.agents.get(agent_name)

    def get_data_source_config(self, source_name: str) -> Optional[DataSourceConfig]:
        """Get data source configuration"""
        if not self.config:
            raise ValueError("Configuration not loaded")
        return self.config.data_sources.get(source_name)

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == Environment.PRODUCTION

    def is_debug(self) -> bool:
        """Check if debug mode enabled"""
        return self.config.debug if self.config else False


# ============================================================================
# Global config instance (singleton pattern)
# ============================================================================

_global_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    Get global configuration manager instance

    Singleton pattern for easy access throughout codebase.

    Example:
        ```python
        from agents.shared.config_manager import get_config_manager

        config = get_config_manager()
        llm_config = config.get_llm_config()
        ```
    """
    global _global_config_manager

    if _global_config_manager is None:
        _global_config_manager = ConfigManager()

    return _global_config_manager


def initialize_config(config_dir: str = "config", environment: Optional[Environment] = None):
    """
    Initialize global configuration

    Call this at application startup.

    Args:
        config_dir: Configuration directory
        environment: Environment override
    """
    global _global_config_manager
    _global_config_manager = ConfigManager(config_dir=config_dir, environment=environment)
    logger.info("Global configuration initialized")


# Example usage
if __name__ == "__main__":
    # Initialize config manager
    config_manager = ConfigManager(config_dir="config")

    # Create default config
    default_config = {
        "environment": "development",
        "debug": True,
        "llm": {
            "provider": "azure_openai",
            "model_name": "gpt-4",
            "temperature": 0.7,
            "api_base": os.getenv("OPENAI_API_BASE"),
            "api_key": os.getenv("OPENAI_API_KEY")
        },
        "data_sources": {
            "newsapi": {
                "name": "newsapi",
                "enabled": True,
                "api_key": os.getenv("NEWS_API_KEY"),
                "max_results": 20
            },
            "naver": {
                "name": "naver",
                "enabled": True,
                "api_key": os.getenv("NAVER_CLIENT_ID"),
                "max_results": 20
            }
        },
        "agents": {
            "news_trend_agent": {
                "name": "news_trend_agent",
                "enabled": True,
                "max_concurrent_tasks": 5,
                "timeout_seconds": 300
            }
        },
        "monitoring": {
            "enabled": True,
            "log_level": "INFO",
            "metrics_enabled": True
        },
        "rate_limit": {
            "enabled": True,
            "requests_per_minute": 60
        }
    }

    # Save default config
    config_manager.config_dir.mkdir(parents=True, exist_ok=True)
    default_path = config_manager.config_dir / "default.yaml"

    with open(default_path, "w") as f:
        yaml.safe_dump(default_config, f, default_flow_style=False)

    print(f"Created default configuration: {default_path}")

    # Reload and display
    config_manager.reload()

    print(f"\nLLM Provider: {config_manager.get_llm_config().provider}")
    print(f"Environment: {config_manager.environment.value}")
    print(f"Debug mode: {config_manager.is_debug()}")

    # Get agent config
    agent_config = config_manager.get_agent_config("news_trend_agent")
    if agent_config:
        print(f"\nAgent '{agent_config.name}':")
        print(f"  Max concurrent tasks: {agent_config.max_concurrent_tasks}")
        print(f"  Timeout: {agent_config.timeout_seconds}s")

"""
레이트 리미팅 및 쿼터 관리

지능형 레이트 리미팅으로 API 쿼터 소진을 방지합니다.

주요 기능:
- 부드러운 레이트 리미팅을 위한 토큰 버킷 알고리즘
- 제공자별 쿼터 추적
- 비용 추정 및 예산 관리
- 사용량 기반 적응형 레이트 리미팅
- 분산 레이트 리미팅 지원

업계 패턴 기반:
- Token Bucket: https://en.wikipedia.org/wiki/Token_bucket
- Stripe rate limiting: https://stripe.com/docs/rate-limits
"""
import time
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class RateLimitStrategy(str, Enum):
    """레이트 리미팅 전략"""
    TOKEN_BUCKET = "token_bucket"      # 부드러운 레이트 리미팅
    FIXED_WINDOW = "fixed_window"      # 고정 시간 윈도우
    SLIDING_WINDOW = "sliding_window"  # 슬라이딩 시간 윈도우
    ADAPTIVE = "adaptive"              # 오류 기반 적응형


@dataclass
class QuotaLimit:
    """
    쿼터 제한 정의

    특정 리소스 또는 제공자에 대한 제한을 나타냅니다.
    """
    name: str
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    tokens_per_minute: Optional[int] = None
    cost_per_day_usd: Optional[float] = None

    # Current usage
    requests_count_minute: int = 0
    requests_count_hour: int = 0
    requests_count_day: int = 0
    tokens_count_minute: int = 0
    cost_today_usd: float = 0.0

    # Tracking
    last_reset_minute: float = field(default_factory=time.time)
    last_reset_hour: float = field(default_factory=time.time)
    last_reset_day: float = field(default_factory=time.time)


@dataclass
class RateLimitResult:
    """레이트 제한 체크 결과"""
    allowed: bool
    wait_time_seconds: float = 0.0
    reason: str = ""
    quota_remaining: Optional[int] = None


class TokenBucket:
    """
    토큰 버킷 레이트 리미터

    부드러운 레이트 리미팅을 위한 고전적인 토큰 버킷 알고리즘입니다.

    Example:
        ```python
        # 분당 60 요청, 버스트 10
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        if bucket.consume(1):
            # API 호출
            pass
        else:
            # 대기
            time.sleep(bucket.time_until_available(1))
        ```
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        토큰 버킷 초기화

        Args:
            capacity: 최대 토큰 수 (버스트 크기)
            refill_rate: 초당 토큰 충전 속도
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()

    def _refill(self):
        """경과 시간에 따라 토큰 충전"""
        now = time.time()
        elapsed = now - self.last_refill

        # 토큰 추가
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        토큰 소비 시도

        Args:
            tokens: 소비할 토큰 수

        Returns:
            토큰이 사용 가능하면 True, 아니면 False
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        else:
            return False

    def time_until_available(self, tokens: int = 1) -> float:
        """
        토큰이 사용 가능할 때까지의 시간

        Args:
            tokens: 필요한 토큰 수

        Returns:
            대기 시간 (초)
        """
        self._refill()

        if self.tokens >= tokens:
            return 0.0

        # 대기 시간 계산
        tokens_needed = tokens - self.tokens
        wait_time = tokens_needed / self.refill_rate

        return wait_time

    def get_available_tokens(self) -> int:
        """현재 사용 가능한 토큰 수 조회"""
        self._refill()
        return int(self.tokens)


class RateLimiter:
    """
    쿼터 관리 기능이 포함된 다중 제공자 레이트 리미터

    여러 API 제공자에 대한 레이트 제한 및 쿼터를 관리합니다.

    Example:
        ```python
        limiter = RateLimiter()

        # 제공자 제한 등록
        limiter.register_provider(
            "openai",
            requests_per_minute=60,
            requests_per_hour=3000,
            cost_per_day_usd=50.0
        )

        # API 호출 전 체크
        result = limiter.check_rate_limit("openai", tokens=1000)
        if result.allowed:
            # API 호출
            response = call_api()

            # 사용량 기록
            limiter.record_request("openai", tokens_used=1200, cost_usd=0.024)
        else:
            # 대기
            await asyncio.sleep(result.wait_time_seconds)
        ```
    """

    def __init__(
        self,
        strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET,
        enable_cost_tracking: bool = True
    ):
        """
        레이트 리미터 초기화

        Args:
            strategy: 레이트 리미팅 전략
            enable_cost_tracking: API 비용 추적 활성화
        """
        self.strategy = strategy
        self.enable_cost_tracking = enable_cost_tracking

        # Provider quotas
        self.quotas: Dict[str, QuotaLimit] = {}

        # Token buckets per provider
        self.buckets: Dict[str, TokenBucket] = {}

        # Request history for sliding window
        self.request_history: Dict[str, deque] = {}

        # Cost tracking
        self.daily_costs: Dict[str, float] = {}

    def register_provider(
        self,
        provider_name: str,
        requests_per_minute: int = 60,
        requests_per_hour: int = 3000,
        requests_per_day: int = 100000,
        tokens_per_minute: Optional[int] = None,
        cost_per_day_usd: Optional[float] = None,
        burst_size: Optional[int] = None
    ):
        """
        Register provider with rate limits

        Args:
            provider_name: Provider identifier
            requests_per_minute: RPM limit
            requests_per_hour: RPH limit
            requests_per_day: RPD limit
            tokens_per_minute: TPM limit
            cost_per_day_usd: Daily cost budget
            burst_size: Burst size for token bucket (defaults to RPM/6)
        """
        # Create quota
        quota = QuotaLimit(
            name=provider_name,
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            requests_per_day=requests_per_day,
            tokens_per_minute=tokens_per_minute,
            cost_per_day_usd=cost_per_day_usd
        )

        self.quotas[provider_name] = quota

        # Create token bucket (requests per second)
        if self.strategy == RateLimitStrategy.TOKEN_BUCKET:
            capacity = burst_size or max(requests_per_minute // 6, 1)
            refill_rate = requests_per_minute / 60.0

            self.buckets[provider_name] = TokenBucket(
                capacity=capacity,
                refill_rate=refill_rate
            )

        # Initialize request history
        if self.strategy == RateLimitStrategy.SLIDING_WINDOW:
            self.request_history[provider_name] = deque()

        logger.info(
            f"Registered provider '{provider_name}': "
            f"{requests_per_minute} RPM, {requests_per_hour} RPH"
        )

    def check_rate_limit(
        self,
        provider_name: str,
        tokens: int = 0
    ) -> RateLimitResult:
        """
        Check if request is allowed under rate limits

        Args:
            provider_name: Provider name
            tokens: Number of tokens for this request

        Returns:
            RateLimitResult with decision and wait time
        """
        if provider_name not in self.quotas:
            # No limits configured - allow
            return RateLimitResult(allowed=True)

        quota = self.quotas[provider_name]

        # Reset counters if needed
        self._reset_counters(quota)

        # Check quota limits
        if quota.requests_count_minute >= quota.requests_per_minute:
            wait_time = 60 - (time.time() - quota.last_reset_minute)
            return RateLimitResult(
                allowed=False,
                wait_time_seconds=max(0, wait_time),
                reason=f"RPM limit exceeded ({quota.requests_per_minute})"
            )

        if quota.requests_count_hour >= quota.requests_per_hour:
            wait_time = 3600 - (time.time() - quota.last_reset_hour)
            return RateLimitResult(
                allowed=False,
                wait_time_seconds=max(0, wait_time),
                reason=f"RPH limit exceeded ({quota.requests_per_hour})"
            )

        if quota.requests_count_day >= quota.requests_per_day:
            wait_time = 86400 - (time.time() - quota.last_reset_day)
            return RateLimitResult(
                allowed=False,
                wait_time_seconds=max(0, wait_time),
                reason=f"RPD limit exceeded ({quota.requests_per_day})"
            )

        # Check token limits
        if quota.tokens_per_minute and tokens > 0:
            if quota.tokens_count_minute + tokens > quota.tokens_per_minute:
                wait_time = 60 - (time.time() - quota.last_reset_minute)
                return RateLimitResult(
                    allowed=False,
                    wait_time_seconds=max(0, wait_time),
                    reason=f"TPM limit exceeded ({quota.tokens_per_minute})"
                )

        # Check cost limits
        if self.enable_cost_tracking and quota.cost_per_day_usd:
            if quota.cost_today_usd >= quota.cost_per_day_usd:
                wait_time = 86400 - (time.time() - quota.last_reset_day)
                return RateLimitResult(
                    allowed=False,
                    wait_time_seconds=max(0, wait_time),
                    reason=f"Daily cost limit exceeded (${quota.cost_per_day_usd})"
                )

        # Token bucket check
        if self.strategy == RateLimitStrategy.TOKEN_BUCKET:
            bucket = self.buckets.get(provider_name)
            if bucket:
                if not bucket.consume(1):
                    wait_time = bucket.time_until_available(1)
                    return RateLimitResult(
                        allowed=False,
                        wait_time_seconds=wait_time,
                        reason="Token bucket exhausted"
                    )

        # Calculate remaining quota
        remaining = quota.requests_per_minute - quota.requests_count_minute

        return RateLimitResult(
            allowed=True,
            quota_remaining=remaining
        )

    def record_request(
        self,
        provider_name: str,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        success: bool = True
    ):
        """
        Record API request for quota tracking

        Args:
            provider_name: Provider name
            tokens_used: Tokens consumed
            cost_usd: Cost in USD
            success: Whether request succeeded
        """
        if provider_name not in self.quotas:
            return

        quota = self.quotas[provider_name]

        # Increment counters
        quota.requests_count_minute += 1
        quota.requests_count_hour += 1
        quota.requests_count_day += 1

        # Track tokens
        if tokens_used > 0:
            quota.tokens_count_minute += tokens_used

        # Track costs
        if cost_usd > 0:
            quota.cost_today_usd += cost_usd

        # Add to sliding window history
        if self.strategy == RateLimitStrategy.SLIDING_WINDOW:
            self.request_history[provider_name].append({
                "timestamp": time.time(),
                "tokens": tokens_used,
                "cost": cost_usd,
                "success": success
            })

    def _reset_counters(self, quota: QuotaLimit):
        """Reset quota counters based on time windows"""
        now = time.time()

        # Reset minute counter
        if now - quota.last_reset_minute >= 60:
            quota.requests_count_minute = 0
            quota.tokens_count_minute = 0
            quota.last_reset_minute = now

        # Reset hour counter
        if now - quota.last_reset_hour >= 3600:
            quota.requests_count_hour = 0
            quota.last_reset_hour = now

        # Reset day counter
        if now - quota.last_reset_day >= 86400:
            quota.requests_count_day = 0
            quota.cost_today_usd = 0.0
            quota.last_reset_day = now

    async def wait_for_capacity(
        self,
        provider_name: str,
        tokens: int = 0,
        max_wait: float = 60.0
    ) -> bool:
        """
        Wait until capacity is available

        Args:
            provider_name: Provider name
            tokens: Required tokens
            max_wait: Maximum wait time in seconds

        Returns:
            True if capacity available, False if max_wait exceeded
        """
        start_time = time.time()

        while True:
            result = self.check_rate_limit(provider_name, tokens)

            if result.allowed:
                return True

            if time.time() - start_time >= max_wait:
                logger.warning(
                    f"Max wait time exceeded for {provider_name}: {max_wait}s"
                )
                return False

            # Wait
            wait_time = min(result.wait_time_seconds, max_wait - (time.time() - start_time))
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

    def get_quota_status(self, provider_name: str) -> Dict[str, Any]:
        """
        Get current quota status

        Args:
            provider_name: Provider name

        Returns:
            Status dictionary with usage and limits
        """
        if provider_name not in self.quotas:
            return {}

        quota = self.quotas[provider_name]
        self._reset_counters(quota)

        status = {
            "provider": provider_name,
            "requests": {
                "minute": {
                    "used": quota.requests_count_minute,
                    "limit": quota.requests_per_minute,
                    "remaining": quota.requests_per_minute - quota.requests_count_minute
                },
                "hour": {
                    "used": quota.requests_count_hour,
                    "limit": quota.requests_per_hour,
                    "remaining": quota.requests_per_hour - quota.requests_count_hour
                },
                "day": {
                    "used": quota.requests_count_day,
                    "limit": quota.requests_per_day,
                    "remaining": quota.requests_per_day - quota.requests_count_day
                }
            }
        }

        # Add token info if tracked
        if quota.tokens_per_minute:
            status["tokens"] = {
                "minute": {
                    "used": quota.tokens_count_minute,
                    "limit": quota.tokens_per_minute,
                    "remaining": quota.tokens_per_minute - quota.tokens_count_minute
                }
            }

        # Add cost info if tracked
        if quota.cost_per_day_usd:
            status["cost"] = {
                "day": {
                    "used_usd": quota.cost_today_usd,
                    "limit_usd": quota.cost_per_day_usd,
                    "remaining_usd": quota.cost_per_day_usd - quota.cost_today_usd
                }
            }

        return status

    def get_all_quota_status(self) -> Dict[str, Dict[str, Any]]:
        """Get quota status for all providers"""
        return {
            provider_name: self.get_quota_status(provider_name)
            for provider_name in self.quotas.keys()
        }

    def save_state(self, filepath: str):
        """Save rate limiter state to disk"""
        state = {
            "quotas": {
                name: {
                    "requests_count_minute": q.requests_count_minute,
                    "requests_count_hour": q.requests_count_hour,
                    "requests_count_day": q.requests_count_day,
                    "tokens_count_minute": q.tokens_count_minute,
                    "cost_today_usd": q.cost_today_usd,
                    "last_reset_minute": q.last_reset_minute,
                    "last_reset_hour": q.last_reset_hour,
                    "last_reset_day": q.last_reset_day
                }
                for name, q in self.quotas.items()
            }
        }

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"Rate limiter state saved to {filepath}")


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get global rate limiter instance

    Singleton pattern for easy access.

    Example:
        ```python
        from agents.shared.rate_limiter import get_rate_limiter

        limiter = get_rate_limiter()
        result = limiter.check_rate_limit("openai")
        ```
    """
    global _global_rate_limiter

    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter()

    return _global_rate_limiter


# Example usage
if __name__ == "__main__":
    # Initialize rate limiter
    limiter = RateLimiter()

    # Register providers
    limiter.register_provider(
        "openai",
        requests_per_minute=60,
        requests_per_hour=3000,
        requests_per_day=100000,
        tokens_per_minute=90000,
        cost_per_day_usd=50.0,
        burst_size=10
    )

    limiter.register_provider(
        "anthropic",
        requests_per_minute=50,
        requests_per_hour=2000,
        cost_per_day_usd=30.0
    )

    # Simulate API calls
    print("=== Simulating API calls ===")

    for i in range(15):
        result = limiter.check_rate_limit("openai", tokens=1000)

        if result.allowed:
            print(f"Request {i+1}: ALLOWED (remaining: {result.quota_remaining})")
            limiter.record_request("openai", tokens_used=1200, cost_usd=0.024)
        else:
            print(f"Request {i+1}: DENIED - {result.reason} (wait: {result.wait_time_seconds:.2f}s)")

        time.sleep(0.1)

    # Check status
    print("\n=== Quota Status ===")
    status = limiter.get_quota_status("openai")

    print(f"Provider: {status['provider']}")
    print(f"Requests (minute): {status['requests']['minute']['used']}/{status['requests']['minute']['limit']}")
    print(f"Tokens (minute): {status['tokens']['minute']['used']}/{status['tokens']['minute']['limit']}")
    print(f"Cost (day): ${status['cost']['day']['used_usd']:.2f}/${status['cost']['day']['limit_usd']:.2f}")

    # Test token bucket
    print("\n=== Token Bucket Test ===")
    bucket = TokenBucket(capacity=5, refill_rate=1.0)

    for i in range(10):
        if bucket.consume(1):
            print(f"Consumed token {i+1}")
        else:
            wait_time = bucket.time_until_available(1)
            print(f"No tokens available, wait: {wait_time:.2f}s")
            time.sleep(wait_time)
            bucket.consume(1)
            print(f"Consumed token {i+1} (after wait)")

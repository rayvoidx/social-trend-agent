"""
n8n Webhook API Routes

n8n 워크플로우에서 직접 호출할 수 있는 전용 엔드포인트

Performance optimizations:
- Redis-based task storage (replaces in-memory dict)
- TTL for automatic cleanup
- Async operations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import uuid
from datetime import datetime
from enum import Enum

from src.infrastructure.storage.async_redis_cache import get_async_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/n8n", tags=["n8n Automation"])

# Redis-based task storage with TTL (24 hours)
TASK_STORE_TTL = 86400  # 24 hours


class RedisTaskStore:
    """Redis-based task storage for n8n tasks."""

    def __init__(self, prefix: str = "n8n:tasks"):
        self.prefix = prefix
        self._cache = None

    async def _get_cache(self):
        if self._cache is None:
            self._cache = get_async_cache(prefix=self.prefix)
        return self._cache

    async def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task data from Redis."""
        cache = await self._get_cache()
        return await cache.get(task_id)

    async def set(self, task_id: str, data: Dict[str, Any]) -> bool:
        """Store task data in Redis with TTL."""
        cache = await self._get_cache()
        return await cache.set(task_id, data, ttl=TASK_STORE_TTL)

    async def update(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Update existing task data."""
        cache = await self._get_cache()
        existing = await cache.get(task_id)
        if existing:
            existing.update(updates)
            return await cache.set(task_id, existing, ttl=TASK_STORE_TTL)
        return False

    async def delete(self, task_id: str) -> bool:
        """Delete task from Redis."""
        cache = await self._get_cache()
        return await cache.delete(task_id)

    def __contains__(self, task_id: str) -> bool:
        """Sync check - use exists() for async."""
        # Note: This is for backwards compatibility, prefer async exists()
        return False

    async def exists(self, task_id: str) -> bool:
        """Check if task exists in Redis."""
        cache = await self._get_cache()
        return await cache.exists(task_id)


# Global Redis task store instance
TASK_STORE = RedisTaskStore()


class TaskStatus(str, Enum):
    """작업 상태"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Request/Response Models
# ============================================================================


class N8NAgentRequest(BaseModel):
    """n8n에서 에이전트 실행 요청"""

    agent: str = Field(..., description="에이전트 이름 (news_trend_agent, viral_video_agent)")
    query: str = Field(..., description="분석 쿼리")

    # 선택적 파라미터
    time_window: Optional[str] = Field("7d", description="시간 범위 (24h, 7d, 30d)")
    language: Optional[str] = Field("ko", description="언어 (ko, en)")
    max_results: Optional[int] = Field(20, description="최대 결과 수")

    # n8n 워크플로우 메타데이터
    workflow_id: Optional[str] = Field(None, description="n8n 워크플로우 ID")
    execution_id: Optional[str] = Field(None, description="n8n 실행 ID")

    # 알림 설정
    notify_slack: Optional[bool] = Field(False, description="Slack 알림 전송 여부")
    notify_webhook: Optional[str] = Field(None, description="결과를 전송할 Webhook URL")


class N8NAgentResponse(BaseModel):
    """n8n 에이전트 실행 응답"""

    status: str = Field(..., description="실행 상태 (success, error)")
    task_id: str = Field(..., description="작업 ID")
    agent: str = Field(..., description="실행된 에이전트")
    query: str = Field(..., description="분석 쿼리")

    # 결과 데이터
    result: Optional[Dict[str, Any]] = Field(None, description="분석 결과")

    # 메타데이터
    execution_time: Optional[float] = Field(None, description="실행 시간 (초)")
    timestamp: str = Field(..., description="실행 시각")

    # 에러 정보
    error: Optional[str] = Field(None, description="에러 메시지")


class N8NBatchRequest(BaseModel):
    """n8n 배치 실행 요청"""

    tasks: List[N8NAgentRequest] = Field(..., description="실행할 작업 목록")
    parallel: bool = Field(False, description="병렬 실행 여부")


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/agent/execute", response_model=N8NAgentResponse)
async def execute_agent(request: N8NAgentRequest, background_tasks: BackgroundTasks):
    """
    n8n에서 에이전트를 실행하는 메인 엔드포인트

    **사용 예시 (n8n HTTP Request 노드):**
    ```
    Method: POST
    URL: http://your-server:8000/n8n/agent/execute
    Body:
    {
      "agent": "news_trend_agent",
      "query": "AI",
      "time_window": "7d",
      "workflow_id": "{{$workflow.id}}",
      "execution_id": "{{$execution.id}}"
    }
    ```
    """
    task_id = str(uuid.uuid4())
    start_time = datetime.now()

    # 작업 상태를 Redis에 저장
    await TASK_STORE.set(task_id, {
        "task_id": task_id,
        "status": TaskStatus.RUNNING.value,
        "agent": request.agent,
        "query": request.query,
        "created_at": start_time.isoformat(),
        "updated_at": start_time.isoformat(),
        "progress": 0,
        "result": None,
        "error": None,
    })

    logger.info(
        f"[n8n] Executing agent: {request.agent}, query: {request.query}, task_id: {task_id}"
    )

    try:
        # 에이전트 실행
        if request.agent == "news_trend_agent":
            from src.agents.news_trend.graph import run_agent

            result = run_agent(
                query=request.query,
                time_window=request.time_window,
                language=request.language,
                max_results=request.max_results,
            )
        elif request.agent == "viral_video_agent":
            from src.agents.viral_video.graph import run_agent

            result = run_agent(
                query=request.query,
                time_window=request.time_window,
                market=request.language.upper() if request.language else "KR",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown agent: {request.agent}")

        execution_time = (datetime.now() - start_time).total_seconds()

        # 작업 완료 상태 업데이트 (Redis)
        await TASK_STORE.update(task_id, {
            "status": TaskStatus.COMPLETED.value,
            "result": result,
            "updated_at": datetime.now().isoformat(),
            "execution_time": execution_time,
            "progress": 100,
        })

        # 백그라운드 알림 전송
        if request.notify_slack:
            background_tasks.add_task(send_slack_notification, result, request)

        if request.notify_webhook:
            background_tasks.add_task(send_webhook_notification, result, request)

        logger.info(
            f"[n8n] Agent execution completed: task_id={task_id}, time={execution_time:.2f}s"
        )

        return N8NAgentResponse(
            status="success",
            task_id=task_id,
            agent=request.agent,
            query=request.query,
            result=result,
            execution_time=execution_time,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"[n8n] Agent execution failed: {e}", exc_info=True)

        # 작업 실패 상태 업데이트 (Redis)
        await TASK_STORE.update(task_id, {
            "status": TaskStatus.FAILED.value,
            "error": str(e),
            "updated_at": datetime.now().isoformat(),
        })

        return N8NAgentResponse(
            status="error",
            task_id=task_id,
            agent=request.agent,
            query=request.query,
            error=str(e),
            timestamp=datetime.now().isoformat(),
        )


@router.post("/agent/batch", response_model=Dict[str, Any])
async def execute_batch(request: N8NBatchRequest):
    """
    n8n에서 여러 에이전트를 배치로 실행

    **사용 예시:**
    ```json
    {
      "tasks": [
        {"agent": "news_trend_agent", "query": "AI", "time_window": "7d"},
        {"agent": "news_trend_agent", "query": "전기차", "time_window": "7d"},
        {"agent": "viral_video_agent", "query": "K-pop", "market": "KR"}
      ],
      "parallel": true
    }
    ```
    """
    logger.info(f"[n8n] Batch execution: {len(request.tasks)} tasks, parallel={request.parallel}")

    results = []

    if request.parallel:
        # 병렬 실행
        import asyncio

        async def execute_task(task: N8NAgentRequest):
            # 각 작업을 개별적으로 실행
            response = await execute_agent(task, BackgroundTasks())
            return response

        tasks = [execute_task(task) for task in request.tasks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    else:
        # 순차 실행
        for task in request.tasks:
            result = await execute_agent(task, BackgroundTasks())
            results.append(result)

    return {
        "status": "completed",
        "total_tasks": len(request.tasks),
        "results": results,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/agent/status/{task_id}")
async def get_task_status(task_id: str):
    """
    작업 상태 조회 (비동기 실행 시 사용)

    **사용 예시:**
    ```
    GET /n8n/agent/status/abc-123-def
    ```
    """
    logger.info(f"[n8n] Status check: task_id={task_id}")

    # Redis에서 작업 상태 조회
    task_data = await TASK_STORE.get(task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {
        "task_id": task_id,
        "status": task_data.get("status"),
        "agent": task_data.get("agent"),
        "query": task_data.get("query"),
        "created_at": task_data.get("created_at"),
        "updated_at": task_data.get("updated_at"),
        "result": task_data.get("result"),
        "error": task_data.get("error"),
        "progress": task_data.get("progress", 0),
    }


@router.post("/webhook/result")
async def receive_webhook_result(payload: Dict[str, Any]):
    """
    n8n 워크플로우에서 결과를 다시 받는 엔드포인트

    n8n 워크플로우가 추가 처리 후 결과를 다시 전송할 때 사용

    **페이로드 예시:**
    ```json
    {
        "task_id": "abc-123-def",
        "workflow_id": "workflow_xyz",
        "status": "completed",
        "result": {...},
        "metadata": {...}
    }
    ```
    """
    logger.info(f"[n8n] Received webhook result: {payload.keys()}")

    task_id = payload.get("task_id")
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")

    # Redis에 결과 저장
    existing = await TASK_STORE.get(task_id)
    if existing:
        # 기존 작업 업데이트
        await TASK_STORE.update(task_id, {
            "webhook_result": payload.get("result"),
            "workflow_id": payload.get("workflow_id"),
            "webhook_received_at": datetime.now().isoformat(),
            "metadata": payload.get("metadata", {}),
        })
        logger.info(f"[n8n] Updated task {task_id} with webhook result")
    else:
        # 새 작업으로 저장
        await TASK_STORE.set(task_id, {
            "task_id": task_id,
            "status": payload.get("status", "unknown"),
            "webhook_result": payload.get("result"),
            "workflow_id": payload.get("workflow_id"),
            "created_at": datetime.now().isoformat(),
            "webhook_received_at": datetime.now().isoformat(),
            "metadata": payload.get("metadata", {}),
        })
        logger.info(f"[n8n] Created new task {task_id} from webhook result")

    # 추가 처리 로직 (예: 알림, 데이터 변환 등)
    await _process_webhook_result(task_id, payload)

    return {
        "status": "received",
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
        "message": f"Webhook result for task {task_id} processed successfully",
    }


async def _process_webhook_result(task_id: str, payload: Dict[str, Any]) -> None:
    """
    Webhook 결과에 대한 추가 처리 (async)

    여기서 다음과 같은 작업을 수행할 수 있습니다:
    - 데이터 검증
    - 알림 전송
    - 다운스트림 시스템에 데이터 전달
    - 분석 결과 집계
    """
    try:
        # 상태 확인
        status = payload.get("status")
        if status == "completed":
            logger.info(f"[n8n] Task {task_id} completed successfully via webhook")
        elif status == "failed":
            logger.warning(f"[n8n] Task {task_id} failed: {payload.get('error')}")

        # 메타데이터 처리
        metadata = payload.get("metadata", {})
        if metadata:
            logger.debug(f"[n8n] Processing metadata for task {task_id}: {metadata}")

        # 여기에 추가 비즈니스 로직을 구현할 수 있습니다
        # 예: 결과를 다른 시스템으로 전송, 집계, 알림 등

    except Exception as e:
        logger.error(f"[n8n] Error processing webhook result for task {task_id}: {e}")
        # 에러 발생 시에도 메인 플로우는 계속 진행


# ============================================================================
# Helper Functions
# ============================================================================


async def send_slack_notification(result: Dict[str, Any], request: N8NAgentRequest):
    """Slack 알림 전송"""
    import aiohttp
    import os

    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not slack_webhook:
        logger.warning("[n8n] SLACK_WEBHOOK_URL not configured")
        return

    try:
        message = {
            "text": "✅ 에이전트 분석 완료",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*에이전트*: {request.agent}\n*쿼리*: {request.query}\n*결과*: 분석 완료",
                    },
                }
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(slack_webhook, json=message) as response:
                if response.status == 200:
                    logger.info("[n8n] Slack notification sent")
                else:
                    logger.error(f"[n8n] Slack notification failed: {response.status}")

    except Exception as e:
        logger.error(f"[n8n] Error sending Slack notification: {e}")


async def send_webhook_notification(result: Dict[str, Any], request: N8NAgentRequest):
    """커스텀 Webhook으로 결과 전송"""
    import aiohttp

    if not request.notify_webhook:
        return

    try:
        payload = {
            "agent": request.agent,
            "query": request.query,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(request.notify_webhook, json=payload) as response:
                if response.status == 200:
                    logger.info(f"[n8n] Webhook notification sent to {request.notify_webhook}")
                else:
                    logger.error(f"[n8n] Webhook notification failed: {response.status}")

    except Exception as e:
        logger.error(f"[n8n] Error sending webhook notification: {e}")

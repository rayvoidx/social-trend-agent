"""
n8n Webhook API Routes

n8n 워크플로우에서 직접 호출할 수 있는 전용 엔드포인트
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/n8n", tags=["n8n Automation"])


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
    
    logger.info(f"[n8n] Executing agent: {request.agent}, query: {request.query}, task_id: {task_id}")
    
    try:
        # 에이전트 실행
        if request.agent == "news_trend_agent":
            from agents.news_trend_agent.graph import run_agent
            result = run_agent(
                query=request.query,
                time_window=request.time_window,
                language=request.language,
                max_results=request.max_results
            )
        elif request.agent == "viral_video_agent":
            from agents.viral_video_agent.graph import run_agent
            result = run_agent(
                query=request.query,
                time_window=request.time_window,
                market=request.language.upper() if request.language else "KR"
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown agent: {request.agent}")
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 백그라운드 알림 전송
        if request.notify_slack:
            background_tasks.add_task(send_slack_notification, result, request)
        
        if request.notify_webhook:
            background_tasks.add_task(send_webhook_notification, result, request)
        
        logger.info(f"[n8n] Agent execution completed: task_id={task_id}, time={execution_time:.2f}s")
        
        return N8NAgentResponse(
            status="success",
            task_id=task_id,
            agent=request.agent,
            query=request.query,
            result=result,
            execution_time=execution_time,
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        logger.error(f"[n8n] Agent execution failed: {e}", exc_info=True)
        
        return N8NAgentResponse(
            status="error",
            task_id=task_id,
            agent=request.agent,
            query=request.query,
            error=str(e),
            timestamp=datetime.now().isoformat()
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
        "timestamp": datetime.now().isoformat()
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
    # TODO: 실제 구현에서는 Redis나 DB에서 작업 상태 조회
    logger.info(f"[n8n] Status check: task_id={task_id}")
    
    return {
        "task_id": task_id,
        "status": "completed",
        "message": "Task status tracking not yet implemented"
    }


@router.post("/webhook/result")
async def receive_webhook_result(payload: Dict[str, Any]):
    """
    n8n 워크플로우에서 결과를 다시 받는 엔드포인트
    
    n8n 워크플로우가 추가 처리 후 결과를 다시 전송할 때 사용
    """
    logger.info(f"[n8n] Received webhook result: {payload.keys()}")
    
    # TODO: 결과 저장 또는 추가 처리
    
    return {
        "status": "received",
        "timestamp": datetime.now().isoformat()
    }


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
            "text": f"✅ 에이전트 분석 완료",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*에이전트*: {request.agent}\n*쿼리*: {request.query}\n*결과*: 분석 완료"
                    }
                }
            ]
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
            "timestamp": datetime.now().isoformat()
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(request.notify_webhook, json=payload) as response:
                if response.status == 200:
                    logger.info(f"[n8n] Webhook notification sent to {request.notify_webhook}")
                else:
                    logger.error(f"[n8n] Webhook notification failed: {response.status}")
    
    except Exception as e:
        logger.error(f"[n8n] Error sending webhook notification: {e}")


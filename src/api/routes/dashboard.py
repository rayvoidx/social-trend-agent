"""
실시간 대시보드 API

에이전트 모니터링 및 메트릭을 위한 FastAPI 기반 API입니다.

엔드포인트:
- GET /api/health - 헬스 체크
- GET /api/metrics - 현재 메트릭
- GET /api/tasks - 태스크 목록
- GET /api/tasks/{task_id} - 태스크 상세 정보
- POST /api/tasks - 새 태스크 제출
- GET /api/statistics - 집계 통계
- WebSocket /ws/metrics - 실시간 메트릭 스트림

사용법:
    uvicorn agents.api.dashboard:app --reload --port 8000
"""

from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Tuple
import asyncio
import json
from datetime import datetime
import logging

from src.infrastructure.distributed import DistributedAgentExecutor, TaskPriority, TaskStatus
from src.infrastructure.monitoring import (
    MetricsAggregator,
    get_metrics as prometheus_generate_latest,
    get_metrics_content_type,
)
from src.infrastructure.storage.async_redis_cache import (
    get_async_cache,
    cache_key_from_request,
)
from src.domain.models import Insight, InsightSource, INSIGHT_REPOSITORY, MISSION_REPOSITORY
from src.domain.models import save_insight_from_result
from src.domain.mission import generate_missions_from_insight, recommend_creators_for_mission
from src.api.routes.n8n import router as n8n_router
from src.api.routes.mcp_routes import router as mcp_router
from src.api.routes.auth_router import router as auth_router

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Agent Dashboard API",
    description="Real-time monitoring and control for consumer trend agents",
    version="4.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(n8n_router)
app.include_router(mcp_router)

# Include auth router
app.include_router(auth_router)

# Global executor (initialized on startup)
executor: Optional[DistributedAgentExecutor] = None

# Global async cache
cache = get_async_cache(prefix="api")


# ============================================================================
# 요청/응답 모델
# ============================================================================


class TaskSubmitRequest(BaseModel):
    """태스크 제출 요청 모델"""

    agent_name: str = Field(
        default="auto",
        description="에이전트 이름 (news_trend_agent|viral_video_agent|social_trend_agent|auto)",
    )
    query: str = Field(..., description="검색 쿼리")
    params: Dict[str, Any] = Field(default_factory=dict, description="추가 파라미터")
    priority: int = Field(default=1, ge=0, le=3, description="우선순위 (0=낮음, 3=긴급)")


class TaskResponse(BaseModel):
    """태스크 응답 모델"""

    task_id: str
    agent_name: str
    query: str
    status: str
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MetricsResponse(BaseModel):
    """메트릭 응답 모델"""

    timestamp: float
    executor_stats: Dict[str, Any]
    recent_tasks: List[Dict[str, Any]]
    performance_summary: Dict[str, Any]


class InsightSummary(BaseModel):
    """인사이트 요약 응답 모델"""

    id: str
    source: str
    query: str
    time_window: Optional[str] = None
    language: Optional[str] = None
    sentiment_summary: Optional[str] = None
    top_keywords: List[str] = []
    run_id: Optional[str] = None
    report_path: Optional[str] = None
    created_at: float


class MissionRecommendRequest(BaseModel):
    """미션 추천 요청 모델"""

    insight_id: str = Field(..., description="추천의 기준이 되는 Insight ID")
    target_audience: Optional[str] = Field(
        default=None, description="선택적 타겟 오디언스(있으면 미션에 반영)"
    )
    budget: Optional[float] = Field(default=None, description="선택적 예산(있으면 미션에 반영)")


# ============================================================================
# 시작/종료 이벤트
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """시작 시 분산 실행기 초기화"""
    global executor

    logger.info("Starting distributed executor...")

    # 에이전트 실행 함수 정의
    async def execute_agent(
        agent_name: str, query: str, params: Dict[str, Any], task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """에이전트 실행 및 결과 반환 (task_id가 있으면 스트리밍 이벤트 발행)"""
        from src.api.streaming import stream_manager, StreamEvent
        from src.agents.stream_utils import run_agent_with_streaming

        # API/웹 환경에서는 stdin 기반 승인(HITL) 입력이 불가능하므로 기본적으로 비활성화
        params = dict(params or {})
        params.setdefault("require_approval", False)

        async def _run_single(
            agent: str, q: str, p: Dict[str, Any]
        ) -> Tuple[InsightSource, Dict[str, Any]]:
            if agent == "news_trend_agent":
                from src.agents.news_trend.graph import run_agent as run_news_agent

                # 스트리밍 모드: task_id가 있으면 graph.stream() 사용
                if task_id:
                    result_state = await run_agent_with_streaming(
                        task_id=task_id,
                        agent_name=agent,
                        run_fn=run_news_agent,
                        query=q,
                        params=p,
                    )
                    return InsightSource.NEWS_TREND, result_state.model_dump()
                return InsightSource.NEWS_TREND, run_news_agent(query=q, **p).model_dump()
            if agent == "viral_video_agent":
                from src.agents.viral_video.graph import run_agent as run_viral_agent

                return InsightSource.VIRAL_VIDEO, run_viral_agent(query=q, **p).model_dump()
            if agent == "social_trend_agent":
                from src.agents.social_trend.graph import run_agent as run_social_agent

                return InsightSource.SOCIAL_TREND, run_social_agent(query=q, **p).model_dump()
            raise ValueError(f"Unknown agent: {agent}")

        # 2025: Orchestrator 3-gear mode (router -> planner -> workers)
        if agent_name == "auto":
            from src.agents.orchestrator import orchestrate_request

            orch = orchestrate_request(
                query=query,
                agent_hint=params.get("agent_hint"),
                time_window=params.get("time_window"),
                language=params.get("language"),
            )
            # routing = orch.get("routing") if isinstance(orch, dict) else {}
            plan = (orch.get("plan") if isinstance(orch, dict) else {}) or {}
            agents = plan.get("agents") if isinstance(plan, dict) else None
            if not isinstance(agents, list) or not agents:
                agents = [{"agent_name": "news_trend_agent", "params": {}}]

            # Strong binding: pass orchestrator output into agent state
            params.setdefault("orchestrator", orch)

            sub_results: List[Dict[str, Any]] = []
            primary_agent = str(
                plan.get("primary_agent") or agents[0].get("agent_name") or "news_trend_agent"
            )
            primary_source: Optional[InsightSource] = None
            primary_result: Optional[Dict[str, Any]] = None

            for item in agents:
                ag = str(item.get("agent_name") or "")
                if ag not in ("news_trend_agent", "viral_video_agent", "social_trend_agent"):
                    continue
                # Worker params = request params + planner params (planner params win)
                worker_params = dict(params)
                planner_params = item.get("params")
                if isinstance(planner_params, dict):
                    worker_params.update(planner_params)
                # ensure orchestrator is passed through explicitly
                worker_params["orchestrator"] = orch
                source, result = await _run_single(ag, query, worker_params)
                sub_results.append({"agent_name": ag, "result": result})
                if ag == primary_agent and primary_result is None:
                    primary_source = source
                    primary_result = result

            # Fallback if primary wasn't executed
            if primary_result is None and sub_results:
                primary_agent = str(sub_results[0].get("agent_name") or "news_trend_agent")
                primary_result = dict(sub_results[0].get("result") or {})
                # best effort source mapping
                primary_source = {
                    "news_trend_agent": InsightSource.NEWS_TREND,
                    "viral_video_agent": InsightSource.VIRAL_VIDEO,
                    "social_trend_agent": InsightSource.SOCIAL_TREND,
                }.get(primary_agent, InsightSource.NEWS_TREND)

            if primary_result is None or primary_source is None:
                raise ValueError("Orchestrator failed to produce a worker result")

            # Optional merge report for multi-agent runs
            combine = str(plan.get("combine") or "single")
            if combine == "merge" and len(sub_results) >= 2:
                try:
                    from src.integrations.llm.llm_client import get_llm_client
                    from src.core.routing import ModelRole, get_model_for_role

                    client = get_llm_client()
                    writer_model = get_model_for_role("orchestrator", ModelRole.WRITER)
                    snippets = []
                    for sr in sub_results:
                        r = sr["result"] or {}
                        snippets.append(
                            f"## {sr['agent_name']}\n"
                            f"- summary: {((r.get('analysis') or {}).get('summary') or '')}\n"
                            f"- report_md: {str(r.get('report_md') or '')[:2000]}\n"
                        )
                    merge_prompt = (
                        "Merge the following agent outputs into ONE coherent Korean report.\n"
                        "Requirements:\n"
                        "- Keep it concise but actionable\n"
                        "- Avoid duplicates\n"
                        "- If conflicting, say '불확실'\n\n"
                        f"User query: {query}\n\n" + "\n\n".join(snippets)
                    )
                    merged_report = client.chat(
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a report merger for a compound AI system.",
                            },
                            {"role": "user", "content": merge_prompt},
                        ],
                        temperature=0.3,
                        max_tokens=1200,
                        model=writer_model,
                    )
                    primary_result["report_md"] = str(merged_report).strip()
                except Exception:
                    # If merge fails, keep primary report.
                    pass

            # Use primary result as the task result, but include sub_results for debugging.
            source = primary_source
            result = primary_result
            result["_sub_results"] = sub_results

        else:
            source, result = await _run_single(agent_name, query, params)

        # JSON 직렬화를 위해 딕셔너리로 변환 (dict로 반환됨)
        result_dict = {
            "query": result.get("query"),
            "time_window": result.get("time_window"),
            "language": result.get("language"),
            "normalized": result.get("normalized"),
            "report_md": result.get("report_md"),
            "analysis": result.get("analysis"),
            "metrics": result.get("metrics"),
            "run_id": result.get("run_id"),
        }

        # 인사이트로 저장
        try:
            insight = save_insight_from_result(source, result_dict)
            result_dict["insight_id"] = insight.id
        except Exception:  # 인사이트 저장 실패가 전체 실행을 막지 않도록
            logger.error("Failed to save insight from agent result", exc_info=True)

        # 스트리밍 완료 이벤트 발행
        if task_id:
            await stream_manager.emit(task_id, StreamEvent(
                event="complete",
                data={"task_id": task_id, "status": "completed"},
            ))

        return result_dict

    # 실행기 생성
    executor = DistributedAgentExecutor(num_workers=4, agent_executor=execute_agent)

    # 워커 시작
    await executor.start()

    logger.info("Distributed executor started with 4 workers")


@app.on_event("shutdown")
async def shutdown_event():
    """종료 시 정리"""
    global executor

    if executor:
        logger.info("Stopping distributed executor...")
        await executor.stop()
        logger.info("Distributed executor stopped")


# ============================================================================
# API 엔드포인트
# ============================================================================


@app.get("/api/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "executor_running": executor is not None,
    }


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    """
    Prometheus scrape endpoint.

    Prometheus in `config/prometheus.yml` scrapes `/metrics` from the `api` service.
    We expose it here to avoid repeated 404s and enable real metrics when
    `prometheus_client` is installed.
    """
    data = prometheus_generate_latest()
    return Response(content=data, media_type=get_metrics_content_type())


@app.get("/api/insights")
async def list_insights(
    source: Optional[str] = Query(
        default=None,
        description="에이전트 소스 필터 (news_trend_agent, viral_video_agent, social_trend_agent)",
    ),
    query: Optional[str] = Query(
        default=None,
        description="쿼리 텍스트 부분 일치 필터",
    ),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    저장된 인사이트 목록 조회

    기본적으로 최신 생성 순으로 정렬된 인사이트 요약 정보를 반환합니다.
    """
    # Generate cache key from query parameters
    cache_key = cache_key_from_request(
        path="/api/insights",
        query_params={"source": source, "query": query, "limit": limit},
    )

    # Try cache first
    cached_result = await cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    insights = list(INSIGHT_REPOSITORY.list())

    # 필터링
    if source:
        try:
            src_enum = InsightSource(source)
            insights = [i for i in insights if i.source == src_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    if query:
        lowered = query.lower()
        insights = [i for i in insights if lowered in i.query.lower()]

    # 정렬 및 제한
    insights.sort(key=lambda i: i.created_at, reverse=True)
    insights = insights[:limit]

    items = [
        InsightSummary(
            id=i.id,
            source=i.source.value,
            query=i.query,
            time_window=i.time_window,
            language=i.language,
            sentiment_summary=i.sentiment_summary,
            top_keywords=i.top_keywords,
            run_id=i.run_id,
            report_path=i.report_path,
            created_at=i.created_at.timestamp(),
        ).model_dump()
        for i in insights
    ]

    result = {"total": len(items), "items": items}

    # Cache for 5 minutes (insights don't change frequently)
    await cache.set(cache_key, result, ttl=300)

    return result


@app.get("/api/insights/{insight_id}", response_model=Insight)
async def get_insight(insight_id: str):
    """
    단일 인사이트 상세 조회
    """
    insight = INSIGHT_REPOSITORY.get(insight_id)
    if not insight:
        raise HTTPException(status_code=404, detail=f"Insight {insight_id} not found")
    return insight


@app.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    현재 메트릭 조회

    실시간 실행기 통계 및 최근 태스크 메트릭을 반환합니다.
    """
    if not executor:
        raise HTTPException(status_code=503, detail="Executor not initialized")

    # Get executor statistics
    stats = await executor.get_statistics()

    # Get recent tasks
    all_tasks = await executor.task_queue.get_all_tasks()
    recent_tasks = sorted(all_tasks, key=lambda t: t.created_at, reverse=True)[:10]

    # Get performance summary
    completed_tasks = [t for t in all_tasks if t.status == TaskStatus.COMPLETED]
    if completed_tasks:
        durations = [
            (t.completed_at - t.started_at)
            for t in completed_tasks
            if t.started_at and t.completed_at
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0
    else:
        avg_duration = 0

    performance_summary = {
        "total_completed": len(completed_tasks),
        "average_duration": avg_duration,
        "success_rate": len(completed_tasks) / len(all_tasks) if all_tasks else 0,
    }

    return MetricsResponse(
        timestamp=datetime.now().timestamp(),
        executor_stats=stats,
        recent_tasks=[t.to_dict() for t in recent_tasks],
        performance_summary=performance_summary,
    )


@app.get("/api/tasks")
async def list_tasks(status: Optional[str] = None, limit: int = 50):
    """
    태스크 목록 조회

    Args:
        status: 상태로 필터링 (pending, running, completed, failed)
        limit: 반환할 최대 태스크 수
    """
    if not executor:
        raise HTTPException(status_code=503, detail="Executor not initialized")

    # Generate cache key
    cache_key = cache_key_from_request(
        path="/api/tasks",
        query_params={"status": status, "limit": limit},
    )

    # Try cache (short TTL since tasks change frequently)
    cached_result = await cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    all_tasks = await executor.task_queue.get_all_tasks()

    # Filter by status if specified
    if status:
        try:
            status_enum = TaskStatus(status)
            tasks = [t for t in all_tasks if t.status == status_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    else:
        tasks = all_tasks

    # Sort by created_at (newest first) and limit
    tasks = sorted(tasks, key=lambda t: t.created_at, reverse=True)[:limit]

    result = {"total": len(tasks), "tasks": [t.to_dict() for t in tasks]}

    # Cache for 30 seconds (tasks change frequently)
    await cache.set(cache_key, result, ttl=30)

    return result


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """
    태스크 상세 정보 조회

    특정 태스크에 대한 상세 정보를 반환합니다.
    """
    if not executor:
        raise HTTPException(status_code=503, detail="Executor not initialized")

    task = await executor.task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Calculate duration if completed
    duration = None
    if task.started_at and task.completed_at:
        duration = task.completed_at - task.started_at

    return TaskResponse(
        task_id=task.task_id,
        agent_name=task.agent_name,
        query=task.query,
        status=task.status.value,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        duration=duration,
        result=task.result,
        error=task.error,
    )


@app.get("/api/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    """
    태스크 실시간 스트리밍 (SSE)

    태스크 실행 중 노드별 진행 이벤트를 Server-Sent Events로 전달합니다.
    이미 완료된 태스크는 히스토리를 리플레이합니다.
    """
    from src.api.streaming import stream_manager

    async def event_generator():
        async for event in stream_manager.subscribe(task_id):
            if event.event == "keepalive":
                yield ": keepalive\n\n"
            else:
                data = json.dumps(event.to_dict(), ensure_ascii=False)
                yield f"event: {event.event}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/tasks", response_model=Dict[str, str])
async def submit_task(request: TaskSubmitRequest, background_tasks: BackgroundTasks):
    """
    새 태스크 제출

    비동기 실행을 위한 태스크를 제출하고 즉시 태스크 ID를 반환합니다.
    """
    if not executor:
        raise HTTPException(status_code=503, detail="Executor not initialized")

    try:
        priority = TaskPriority(request.priority)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {request.priority}")

    # Submit task
    task_id = await executor.submit_task(
        agent_name=request.agent_name, query=request.query, params=request.params, priority=priority
    )

    # Invalidate tasks cache
    await cache.invalidate_pattern("tasks:*")

    return {
        "task_id": task_id,
        "status": "submitted",
        "message": f"Task submitted successfully. Check /api/tasks/{task_id} for status.",
    }


@app.post("/api/tasks/batch")
async def submit_batch(tasks: List[TaskSubmitRequest]):
    """
    태스크 일괄 제출

    여러 태스크를 한 번에 제출합니다.
    """
    if not executor:
        raise HTTPException(status_code=503, detail="Executor not initialized")

    task_defs = [
        {"agent_name": task.agent_name, "query": task.query, "params": task.params}
        for task in tasks
    ]

    task_ids = await executor.submit_batch(task_defs, priority=TaskPriority.NORMAL)

    return {
        "task_ids": task_ids,
        "count": len(task_ids),
        "message": f"Submitted {len(task_ids)} tasks",
    }


@app.get("/api/statistics")
async def get_statistics():
    """
    집계 통계 조회

    모든 에이전트와 태스크에 대한 종합 통계를 반환합니다.
    """
    if not executor:
        raise HTTPException(status_code=503, detail="Executor not initialized")

    # Try cache first (expensive operation)
    cache_key = "statistics:summary"
    cached_result = await cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # Executor stats
    executor_stats = await executor.get_statistics()

    # Task statistics
    all_tasks = await executor.task_queue.get_all_tasks()

    tasks_by_agent = {}
    for task in all_tasks:
        if task.agent_name not in tasks_by_agent:
            tasks_by_agent[task.agent_name] = []
        tasks_by_agent[task.agent_name].append(task)

    agent_stats = {}
    for agent_name, tasks in tasks_by_agent.items():
        completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in tasks if t.status == TaskStatus.FAILED]

        agent_stats[agent_name] = {
            "total": len(tasks),
            "completed": len(completed),
            "failed": len(failed),
            "success_rate": len(completed) / len(tasks) if tasks else 0,
        }

    # Performance metrics from file system
    try:
        aggregator = MetricsAggregator()
        perf_stats = {}
        for agent_name in tasks_by_agent.keys():
            metrics_list = aggregator.load_all_metrics(agent_name)
            if metrics_list:
                perf_stats[agent_name] = aggregator.compute_statistics(metrics_list)
    except Exception:
        perf_stats = {}

    result = {
        "timestamp": datetime.now().isoformat(),
        "executor": executor_stats,
        "agents": agent_stats,
        "performance": perf_stats,
    }

    # Cache for 60 seconds (expensive to compute)
    await cache.set(cache_key, result, ttl=60)

    return result


@app.post("/api/missions/recommend")
async def recommend_missions(request: MissionRecommendRequest):
    """
    인사이트 기반 미션 및 크리에이터 추천

    1. 주어진 insight_id 로 Insight를 조회
    2. Insight에서 1~2개의 Mission 을 생성
    3. 각 Mission 에 대해 적합한 Creator 리스트를 추천
    """
    insight = INSIGHT_REPOSITORY.get(request.insight_id)
    if not insight:
        raise HTTPException(status_code=404, detail=f"Insight {request.insight_id} not found")

    missions = generate_missions_from_insight(insight)

    # 요청에서 전달된 속성 덮어쓰기 (타겟, 예산)
    for m in missions:
        if request.target_audience:
            m.target_audience = request.target_audience
        if request.budget is not None:
            m.budget = request.budget
        m.updated_at = datetime.utcnow()
        # 저장소 업데이트
        MISSION_REPOSITORY.create(m)

    recommendations: List[Dict[str, Any]] = []
    for m in missions:
        creators = recommend_creators_for_mission(m)
        recommendations.append(
            {
                "mission": m,
                "creators": creators,
            }
        )

    return {
        "insight_id": insight.id,
        "count": len(recommendations),
        "recommendations": recommendations,
    }


@app.get("/api/dashboard/summary")
async def dashboard_summary(limit: int = 10):
    """최근 태스크 기반 요약(에이전트별 집계 + 최근 리포트 경로)"""
    if not executor:
        raise HTTPException(status_code=503, detail="Executor not initialized")

    all_tasks = await executor.task_queue.get_all_tasks()
    tasks = sorted(all_tasks, key=lambda t: t.created_at, reverse=True)[:limit]

    by_agent: Dict[str, Dict[str, Any]] = {}
    for t in tasks:
        ag = t.agent_name
        if ag not in by_agent:
            by_agent[ag] = {"count": 0, "completed": 0, "failed": 0, "latest_report": None}
        by_agent[ag]["count"] += 1
        if t.status == TaskStatus.COMPLETED:
            by_agent[ag]["completed"] += 1
        if t.status == TaskStatus.FAILED:
            by_agent[ag]["failed"] += 1
        if t.result and t.result.get("report_md"):
            by_agent[ag]["latest_report"] = t.result.get("report_md")

    return {"agents": by_agent, "recent_tasks": [t.to_dict() for t in tasks]}


# ============================================================================
# 실시간 업데이트를 위한 WebSocket 엔드포인트
# ============================================================================


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """
    실시간 메트릭 스트리밍을 위한 WebSocket 엔드포인트

    2초마다 메트릭 업데이트를 전송합니다.

    클라이언트 예제:
        ```javascript
        const ws = new WebSocket('ws://localhost:8000/ws/metrics');
        ws.onmessage = (event) => {
            const metrics = JSON.parse(event.data);
            console.log('Metrics:', metrics);
        };
        ```
    """
    await websocket.accept()

    try:
        while True:
            # Get current metrics
            if executor:
                stats = await executor.get_statistics()
                all_tasks = await executor.task_queue.get_all_tasks()
                recent_tasks = sorted(all_tasks, key=lambda t: t.created_at, reverse=True)[:5]

                # Send metrics
                await websocket.send_json(
                    {
                        "timestamp": datetime.now().timestamp(),
                        "stats": stats,
                        "recent_tasks": [t.to_dict() for t in recent_tasks],
                    }
                )

            # Wait before next update
            await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ============================================================================
# 추가 유틸리티 엔드포인트
# ============================================================================


@app.delete("/api/tasks/{task_id}")
async def cancel_task(task_id: str):
    """
    대기 중인 태스크 취소

    참고: 대기 중인 태스크만 취소 가능하며, 실행 중인 태스크는 취소할 수 없습니다.
    """
    if not executor:
        raise HTTPException(status_code=503, detail="Executor not initialized")

    task = await executor.task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status != TaskStatus.PENDING:
        raise HTTPException(
            status_code=400, detail=f"Cannot cancel task in status: {task.status.value}"
        )

    await executor.task_queue.update_task(task_id, status=TaskStatus.CANCELLED)

    return {"message": f"Task {task_id} cancelled"}


@app.get("/api/workers")
async def get_workers():
    """
    워커 정보 조회

    모든 워커에 대한 정보를 반환합니다.
    """
    if not executor:
        raise HTTPException(status_code=503, detail="Executor not initialized")

    workers_info = []
    for worker in executor.workers:
        workers_info.append(
            {
                "worker_id": worker.worker_id,
                "is_running": worker.is_running,
                "current_task": worker.current_task.task_id if worker.current_task else None,
            }
        )

    return {"total_workers": len(workers_info), "workers": workers_info}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agents.api.dashboard:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )

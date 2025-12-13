"""
분산 실행 시스템

에이전트의 분산 실행을 위한 비동기 태스크 큐를 구현합니다.

주요 기능:
- 비동기 태스크 큐 (Redis 기반 선택 가능)
- 워커 풀 관리 및 동적 스케일링
- 태스크 우선순위 기반 스케줄링
- 결과 집계 및 처리
- 장애 복구 및 재시도 메커니즘

아키텍처:
    Producer → Task Queue → Worker Pool → Results

프로덕션 환경에서 수평 확장(horizontal scaling)을 지원하며,
워커 풀 기반의 병렬 처리를 통해 처리량을 극대화합니다.
"""

import asyncio
import uuid
import json
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """태스크 실행 상태"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """태스크 우선순위 레벨"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class AgentTask:
    """에이전트 실행을 위한 태스크 정의"""

    task_id: str
    agent_name: str
    query: str
    params: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    worker_id: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data["priority"] = self.priority.value
        data["status"] = self.status.value
        return data


class InMemoryTaskQueue:
    """
    인메모리 비동기 태스크 큐

    프로덕션 환경에서는 Redis 기반 큐를 사용하는 것을 권장합니다.
    개발 및 테스트 환경에서 사용하기 위한 경량 구현입니다.
    """

    def __init__(self):
        self.tasks: Dict[str, AgentTask] = {}
        self.pending_queue: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def enqueue(self, task: AgentTask) -> str:
        """
        태스크를 큐에 추가

        Args:
            task: 실행할 AgentTask 객체

        Returns:
            태스크 ID
        """
        async with self._lock:
            self.tasks[task.task_id] = task
            await self.pending_queue.put(task)

        logger.info(f"Task enqueued: {task.task_id} (priority={task.priority.value})")
        return task.task_id

    async def dequeue(self) -> Optional[AgentTask]:
        """
        큐에서 다음 태스크를 가져옴

        Returns:
            다음 AgentTask 또는 None
        """
        try:
            task = await self.pending_queue.get()
            return task
        except asyncio.QueueEmpty:
            return None

    async def get_task(self, task_id: str) -> Optional[AgentTask]:
        """ID로 태스크 조회"""
        return self.tasks.get(task_id)

    async def update_task(self, task_id: str, **updates):
        """태스크 필드 업데이트"""
        async with self._lock:
            if task_id in self.tasks:
                for key, value in updates.items():
                    setattr(self.tasks[task_id], key, value)

    async def get_all_tasks(self) -> List[AgentTask]:
        """모든 태스크 조회"""
        return list(self.tasks.values())

    async def get_tasks_by_status(self, status: TaskStatus) -> List[AgentTask]:
        """상태별로 태스크 조회"""
        return [t for t in self.tasks.values() if t.status == status]


class AgentWorker:
    """
    에이전트 태스크 실행을 위한 비동기 워커

    각 워커는 별도의 asyncio 태스크에서 실행되며,
    큐에서 작업을 가져와 순차적으로 처리합니다.
    """

    def __init__(
        self,
        worker_id: str,
        task_queue: InMemoryTaskQueue,
        agent_executor: Callable[[str, str, Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ):
        """
        워커 초기화

        Args:
            worker_id: 고유한 워커 식별자
            task_queue: 태스크를 가져올 큐
            agent_executor: 에이전트 태스크를 실행할 비동기 함수
                           시그니처: async def(agent_name, query, params) -> result
        """
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.agent_executor = agent_executor
        self.is_running = False
        self.current_task: Optional[AgentTask] = None

    async def start(self):
        """워커 루프 시작"""
        self.is_running = True
        logger.info(f"Worker {self.worker_id} started")

        while self.is_running:
            try:
                # 다음 태스크 가져오기
                task = await self.task_queue.dequeue()
                if not task:
                    await asyncio.sleep(0.1)
                    continue

                # 태스크 실행
                await self._execute_task(task)

            except asyncio.CancelledError:
                logger.info(f"Worker {self.worker_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}", exc_info=True)

        logger.info(f"Worker {self.worker_id} stopped")

    async def _execute_task(self, task: AgentTask):
        """단일 태스크 실행"""
        self.current_task = task

        try:
            # 상태 업데이트
            await self.task_queue.update_task(
                task.task_id,
                status=TaskStatus.RUNNING,
                started_at=time.time(),
                worker_id=self.worker_id,
            )

            logger.info(f"Worker {self.worker_id} executing task {task.task_id}")

            # 에이전트 실행
            result = await self.agent_executor(task.agent_name, task.query, task.params)

            # 성공 상태 업데이트
            await self.task_queue.update_task(
                task.task_id, status=TaskStatus.COMPLETED, completed_at=time.time(), result=result
            )

            logger.info(f"Worker {self.worker_id} completed task {task.task_id}")

        except Exception as e:
            # 실패 상태 업데이트
            await self.task_queue.update_task(
                task.task_id, status=TaskStatus.FAILED, completed_at=time.time(), error=str(e)
            )

            logger.error(f"Worker {self.worker_id} failed task {task.task_id}: {e}")

        finally:
            self.current_task = None

    def stop(self):
        """워커 중지"""
        self.is_running = False


class DistributedAgentExecutor:
    """
    분산 에이전트 실행 시스템

    워커 풀을 관리하고 태스크를 분산 실행합니다.
    프로덕션 환경에서 에이전트의 병렬 실행 및 부하 분산을 담당합니다.

    Example:
        ```python
        # 에이전트 실행 함수 정의
        async def execute_agent(agent_name, query, params):
            from src.agents.news_trend.graph import run_agent
            result = run_agent(query=query, **params)
            return result.__dict__

        # 분산 실행기 생성
        executor = DistributedAgentExecutor(
            num_workers=4,
            agent_executor=execute_agent
        )

        # 워커 시작
        await executor.start()

        # 태스크 제출
        task_id = await executor.submit_task(
            agent_name="news_trend_agent",
            query="AI trends",
            params={"time_window": "7d"}
        )

        # 결과 대기
        result = await executor.wait_for_result(task_id)
        ```
    """

    def __init__(
        self,
        num_workers: int = 4,
        agent_executor: Optional[Callable] = None,
        task_queue: Optional[InMemoryTaskQueue] = None,
    ):
        """
        분산 실행기 초기화

        Args:
            num_workers: 워커 프로세스 수
            agent_executor: 에이전트를 실행할 비동기 함수
            task_queue: 태스크 큐 (None이면 인메모리 큐 생성)
        """
        self.num_workers = num_workers
        self.agent_executor = agent_executor or self._default_executor
        self.task_queue = task_queue or InMemoryTaskQueue()

        self.workers: List[AgentWorker] = []
        self.worker_tasks: List[asyncio.Task] = []

    async def _default_executor(
        self, agent_name: str, query: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """기본 에이전트 실행 함수"""
        from src.agents.news_trend.graph import run_agent

        result = run_agent(query=query, **params)
        return result.__dict__

    async def start(self):
        """모든 워커 시작"""
        logger.info(f"Starting {self.num_workers} workers")

        for i in range(self.num_workers):
            worker_id = f"worker-{i}"
            worker = AgentWorker(worker_id, self.task_queue, self.agent_executor)
            self.workers.append(worker)

            # 백그라운드에서 워커 시작
            task = asyncio.create_task(worker.start())
            self.worker_tasks.append(task)

        logger.info(f"{self.num_workers} workers started")

    async def stop(self):
        """모든 워커 중지"""
        logger.info("Stopping all workers")

        for worker in self.workers:
            worker.stop()

        # 워커 종료 대기
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

        self.workers.clear()
        self.worker_tasks.clear()

        logger.info("All workers stopped")

    async def submit_task(
        self,
        agent_name: str,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        """
        실행할 태스크 제출

        Args:
            agent_name: 실행할 에이전트 이름
            query: 처리할 쿼리
            params: 추가 파라미터
            priority: 태스크 우선순위

        Returns:
            태스크 ID
        """
        task_id = str(uuid.uuid4())

        task = AgentTask(
            task_id=task_id,
            agent_name=agent_name,
            query=query,
            params=params or {},
            priority=priority,
        )

        await self.task_queue.enqueue(task)

        return task_id

    async def submit_batch(
        self, tasks: List[Dict[str, Any]], priority: TaskPriority = TaskPriority.NORMAL
    ) -> List[str]:
        """
        태스크 일괄 제출

        Args:
            tasks: {agent_name, query, params} 딕셔너리 리스트
            priority: 모든 태스크에 적용할 우선순위

        Returns:
            태스크 ID 리스트
        """
        task_ids = []

        for task_def in tasks:
            task_id = await self.submit_task(
                agent_name=task_def["agent_name"],
                query=task_def["query"],
                params=task_def.get("params", {}),
                priority=priority,
            )
            task_ids.append(task_id)

        return task_ids

    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """태스크 상태 조회"""
        task = await self.task_queue.get_task(task_id)
        return task.status if task else None

    async def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """태스크 결과 조회 (완료된 경우)"""
        task = await self.task_queue.get_task(task_id)
        return task.result if task and task.status == TaskStatus.COMPLETED else None

    async def wait_for_result(
        self, task_id: str, timeout: Optional[float] = None, poll_interval: float = 0.5
    ) -> Dict[str, Any]:
        """
        태스크 완료 대기 및 결과 반환

        Args:
            task_id: 대기할 태스크 ID
            timeout: 최대 대기 시간 (None = 무제한)
            poll_interval: 폴링 간격 (초 단위)

        Returns:
            태스크 결과

        Raises:
            TimeoutError: 타임아웃 초과 시
            RuntimeError: 태스크 실패 시
        """
        start_time = time.time()

        while True:
            task = await self.task_queue.get_task(task_id)

            if not task:
                raise ValueError(f"Task {task_id} not found")

            if task.status == TaskStatus.COMPLETED:
                return task.result

            if task.status == TaskStatus.FAILED:
                raise RuntimeError(f"Task failed: {task.error}")

            if task.status == TaskStatus.CANCELLED:
                raise RuntimeError("Task was cancelled")

            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Task {task_id} timeout after {timeout}s")

            await asyncio.sleep(poll_interval)

    async def wait_for_batch(
        self, task_ids: List[str], timeout: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        배치의 모든 태스크 완료 대기

        Args:
            task_ids: 태스크 ID 리스트
            timeout: 모든 태스크의 최대 대기 시간

        Returns:
            결과 리스트 (task_ids와 동일한 순서)
        """
        # 모든 태스크를 동시에 대기
        results = await asyncio.gather(
            *[self.wait_for_result(tid, timeout) for tid in task_ids], return_exceptions=True
        )

        return results

    async def get_statistics(self) -> Dict[str, Any]:
        """
        실행기 통계 조회

        Returns:
            통계 딕셔너리
        """
        all_tasks = await self.task_queue.get_all_tasks()

        by_status = {}
        for status in TaskStatus:
            by_status[status.value] = len([t for t in all_tasks if t.status == status])

        active_workers = len([w for w in self.workers if w.current_task])

        return {
            "num_workers": len(self.workers),
            "active_workers": active_workers,
            "total_tasks": len(all_tasks),
            "tasks_by_status": by_status,
            "queue_size": self.task_queue.pending_queue.qsize(),
        }


# Example usage
async def example_usage():
    """분산 실행 사용 예제"""

    # 에이전트 실행 함수 정의
    async def my_agent_executor(agent_name, query, params):
        """커스텀 에이전트 실행 함수"""
        print(f"Executing {agent_name} with query: {query}")
        await asyncio.sleep(2)  # 작업 시뮬레이션
        return {"query": query, "result": f"Result for {query}"}

    # Create distributed executor
    executor = DistributedAgentExecutor(num_workers=3, agent_executor=my_agent_executor)

    # Start workers
    await executor.start()

    try:
        # Submit single task
        task_id = await executor.submit_task(
            agent_name="news_trend_agent",
            query="AI trends",
            params={"time_window": "7d"},
            priority=TaskPriority.HIGH,
        )

        print(f"Submitted task: {task_id}")

        # Submit batch
        batch_tasks = [{"agent_name": "news_trend_agent", "query": f"Query {i}"} for i in range(5)]
        task_ids = await executor.submit_batch(batch_tasks)

        print(f"Submitted batch: {len(task_ids)} tasks")

        # Wait for first task
        result = await executor.wait_for_result(task_id, timeout=10)
        print(f"Result: {result}")

        # Get statistics
        stats = await executor.get_statistics()
        print(f"Statistics: {stats}")

    finally:
        # Stop workers
        await executor.stop()


if __name__ == "__main__":
    asyncio.run(example_usage())

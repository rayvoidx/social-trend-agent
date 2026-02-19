"""
SSE 스트리밍을 위한 TaskStreamManager

태스크 실행 중 노드별 진행 이벤트를 pub/sub 방식으로 전달합니다.
"""

import asyncio
import time
import logging
from typing import Dict, Any, AsyncGenerator, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """스트리밍 이벤트"""
    event: str  # node_start, node_complete, error, complete
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TaskStreamManager:
    """
    태스크별 SSE 이벤트 관리자

    - emit(): 워커가 이벤트 발행
    - subscribe(): SSE 엔드포인트가 이벤트 소비 (async generator)
    - 히스토리 리플레이: 늦게 연결해도 지난 이벤트 수신
    - 타임아웃 기반 자동 정리
    """

    def __init__(self, timeout: float = 120.0, cleanup_delay: float = 60.0):
        self._streams: Dict[str, asyncio.Queue] = {}
        self._history: Dict[str, list] = {}
        self._completed: Dict[str, float] = {}  # task_id -> completed_at
        self._timeout = timeout
        self._cleanup_delay = cleanup_delay
        self._lock = asyncio.Lock()

    async def emit(self, task_id: str, event: StreamEvent):
        """이벤트 발행"""
        async with self._lock:
            if task_id not in self._history:
                self._history[task_id] = []
            self._history[task_id].append(event)

            if task_id in self._streams:
                try:
                    self._streams[task_id].put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(f"Stream queue full for task {task_id}")

        if event.event in ("complete", "error"):
            self._completed[task_id] = time.time()
            # Schedule cleanup
            asyncio.get_event_loop().call_later(
                self._cleanup_delay, lambda tid=task_id: asyncio.ensure_future(self._cleanup(tid))
            )

    async def subscribe(self, task_id: str) -> AsyncGenerator[StreamEvent, None]:
        """
        이벤트 구독 (async generator)

        이미 발행된 히스토리를 먼저 리플레이한 후, 실시간 이벤트를 스트리밍합니다.
        """
        # Snapshot history and create a fresh queue under the lock
        async with self._lock:
            history = list(self._history.get(task_id, []))
            # Create a NEW queue so it only receives events emitted AFTER this point
            queue: asyncio.Queue = asyncio.Queue(maxsize=100)
            self._streams[task_id] = queue

        # Replay history snapshot
        for event in history:
            yield event
            if event.event in ("complete", "error"):
                return

        # Stream real-time events (only new ones, not duplicates of history)
        start = time.time()
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield event
                if event.event in ("complete", "error"):
                    return
            except asyncio.TimeoutError:
                # Send keepalive
                yield StreamEvent(event="keepalive", data={})
                if time.time() - start > self._timeout:
                    return

    async def _cleanup(self, task_id: str):
        """완료된 태스크의 스트림 정리"""
        async with self._lock:
            self._streams.pop(task_id, None)
            self._history.pop(task_id, None)
            self._completed.pop(task_id, None)
        logger.debug(f"Cleaned up stream for task {task_id}")

    def is_active(self, task_id: str) -> bool:
        """태스크 스트림이 활성 상태인지 확인"""
        return task_id in self._history


# Global singleton
stream_manager = TaskStreamManager()

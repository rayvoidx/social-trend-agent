"""
성능 모니터링 및 메트릭 수집

에이전트의 성능, 리소스 사용량, 품질 메트릭을 추적합니다.

주요 기능:
- 실행 시간 추적
- 리소스 사용량 모니터링
- 품질 메트릭 수집
- 성능 이력 관리
"""

import time
import psutil
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """단일 에이전트 실행의 성능 메트릭"""

    run_id: str
    agent_name: str
    query: str
    start_time: float
    end_time: float
    duration_seconds: float

    # 리소스 사용량
    cpu_percent: float
    memory_mb: float
    peak_memory_mb: float

    # 데이터 메트릭
    items_collected: int
    items_normalized: int
    items_analyzed: int

    # 품질 메트릭
    coverage: float
    factuality: float
    actionability: float

    # 노드별 타이밍
    node_timings: Dict[str, float]

    # 에러
    error_count: int
    retry_count: int
    partial_completion: bool

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)


class PerformanceMonitor:
    """
    에이전트 실행을 위한 성능 모니터

    실행 시간, 리소스 사용량, 품질 메트릭을 추적합니다.

    Example:
        ```python
        monitor = PerformanceMonitor("news_trend_agent", run_id)

        with monitor.track_node("collect"):
            # ... 노드 실행 ...
            pass

        monitor.record_data_collected(items_count=50)
        monitor.record_quality_metrics(coverage=0.9, factuality=1.0)

        metrics = monitor.finalize()
        monitor.save_metrics()
        ```
    """

    def __init__(self, agent_name: str, run_id: str, query: str = ""):
        """
        성능 모니터 초기화

        Args:
            agent_name: 에이전트 이름
            run_id: 고유 실행 식별자
            query: 처리 중인 쿼리
        """
        self.agent_name = agent_name
        self.run_id = run_id
        self.query = query

        self.start_time = time.time()
        self.end_time: Optional[float] = None

        # 리소스 추적
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = self.initial_memory

        # 데이터 메트릭
        self.items_collected = 0
        self.items_normalized = 0
        self.items_analyzed = 0

        # 품질 메트릭
        self.coverage = 0.0
        self.factuality = 0.0
        self.actionability = 0.0

        # 노드별 타이밍
        self.node_timings: Dict[str, float] = {}
        self.current_node: Optional[str] = None
        self.current_node_start: Optional[float] = None

        # 에러
        self.error_count = 0
        self.retry_count = 0
        self.partial_completion = False

    def track_node(self, node_name: str):
        """
        노드 실행 시간 추적을 위한 컨텍스트 매니저

        Example:
            ```python
            with monitor.track_node("collect"):
                # ... 노드 실행 ...
                pass
            ```
        """

        class NodeTracker:
            def __init__(self, monitor: "PerformanceMonitor", name: str):
                self.monitor = monitor
                self.name = name

            def __enter__(self):
                self.monitor.current_node = self.name
                self.monitor.current_node_start = time.time()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.monitor.current_node_start:
                    duration = time.time() - self.monitor.current_node_start
                    self.monitor.node_timings[self.name] = duration

                    # 피크 메모리 업데이트
                    current_memory = self.monitor.process.memory_info().rss / 1024 / 1024
                    self.monitor.peak_memory = max(self.monitor.peak_memory, current_memory)

                self.monitor.current_node = None
                self.monitor.current_node_start = None

                # 에러 추적
                if exc_type is not None:
                    self.monitor.error_count += 1

        return NodeTracker(self, node_name)

    def record_data_collected(self, items_count: int):
        """수집된 항목 수 기록"""
        self.items_collected = items_count

    def record_data_normalized(self, items_count: int):
        """정규화된 항목 수 기록"""
        self.items_normalized = items_count

    def record_data_analyzed(self, items_count: int):
        """분석된 항목 수 기록"""
        self.items_analyzed = items_count

    def record_quality_metrics(
        self, coverage: float = 0.0, factuality: float = 0.0, actionability: float = 0.0
    ):
        """
        품질 메트릭 기록

        Args:
            coverage: 데이터 커버리지 (0.0-1.0)
            factuality: 사실 정확도 (0.0-1.0)
            actionability: 실행 가능성 점수 (0.0-1.0)
        """
        self.coverage = coverage
        self.factuality = factuality
        self.actionability = actionability

    def record_retry(self):
        """재시도 시도 기록"""
        self.retry_count += 1

    def record_partial_completion(self):
        """부분 완료 기록"""
        self.partial_completion = True

    def finalize(self) -> PerformanceMetrics:
        """
        메트릭 수집 완료

        Returns:
            PerformanceMetrics 객체
        """
        self.end_time = time.time()
        duration = self.end_time - self.start_time

        # 최종 리소스 사용량 조회
        cpu_percent = self.process.cpu_percent()
        current_memory = self.process.memory_info().rss / 1024 / 1024

        metrics = PerformanceMetrics(
            run_id=self.run_id,
            agent_name=self.agent_name,
            query=self.query,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_seconds=duration,
            cpu_percent=cpu_percent,
            memory_mb=current_memory,
            peak_memory_mb=self.peak_memory,
            items_collected=self.items_collected,
            items_normalized=self.items_normalized,
            items_analyzed=self.items_analyzed,
            coverage=self.coverage,
            factuality=self.factuality,
            actionability=self.actionability,
            node_timings=self.node_timings,
            error_count=self.error_count,
            retry_count=self.retry_count,
            partial_completion=self.partial_completion,
        )

        logger.info(
            f"Performance metrics finalized: "
            f"duration={duration:.2f}s, "
            f"memory={current_memory:.1f}MB, "
            f"items={self.items_collected}"
        )

        return metrics

    def save_metrics(self, metrics_dir: str = "artifacts/metrics"):
        """
        메트릭을 디스크에 저장

        Args:
            metrics_dir: 메트릭을 저장할 디렉토리
        """
        metrics = self.finalize()

        # 디렉토리 생성
        metrics_path = Path(metrics_dir)
        metrics_path.mkdir(parents=True, exist_ok=True)

        # JSON 파일로 저장
        timestamp = datetime.fromtimestamp(self.start_time).strftime("%Y%m%d_%H%M%S")
        filename = f"{self.agent_name}_{timestamp}_{self.run_id[:8]}.json"
        filepath = metrics_path / filename

        with open(filepath, "w") as f:
            json.dump(metrics.to_dict(), f, indent=2)

        logger.info(f"Metrics saved to {filepath}")

        return filepath


class MetricsAggregator:
    """
    여러 실행에 걸친 메트릭 집계

    성능 분석 및 트렌드 분석을 제공합니다.
    """

    def __init__(self, metrics_dir: str = "artifacts/metrics"):
        """
        메트릭 집계기 초기화

        Args:
            metrics_dir: 메트릭 파일이 포함된 디렉토리
        """
        self.metrics_dir = Path(metrics_dir)

    def load_all_metrics(self, agent_name: Optional[str] = None) -> List[PerformanceMetrics]:
        """
        디스크에서 모든 메트릭 로드

        Args:
            agent_name: 에이전트 이름으로 필터링 (선택사항)

        Returns:
            PerformanceMetrics 리스트
        """
        if not self.metrics_dir.exists():
            return []

        metrics_list = []
        pattern = f"{agent_name}_*.json" if agent_name else "*.json"

        for filepath in self.metrics_dir.glob(pattern):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                metrics_list.append(PerformanceMetrics(**data))
            except Exception as e:
                logger.warning(f"Failed to load metrics from {filepath}: {e}")

        return metrics_list

    def compute_statistics(self, metrics_list: List[PerformanceMetrics]) -> Dict[str, Any]:
        """
        메트릭으로부터 통계 계산

        Args:
            metrics_list: PerformanceMetrics 리스트

        Returns:
            통계가 포함된 딕셔너리
        """
        if not metrics_list:
            return {}

        durations = [m.duration_seconds for m in metrics_list]
        memories = [m.peak_memory_mb for m in metrics_list]
        coverages = [m.coverage for m in metrics_list]
        factualities = [m.factuality for m in metrics_list]

        stats = {
            "total_runs": len(metrics_list),
            "duration": {
                "mean": sum(durations) / len(durations),
                "min": min(durations),
                "max": max(durations),
                "p50": sorted(durations)[len(durations) // 2],
                "p95": (
                    sorted(durations)[int(len(durations) * 0.95)]
                    if len(durations) > 20
                    else max(durations)
                ),
            },
            "memory": {
                "mean": sum(memories) / len(memories),
                "min": min(memories),
                "max": max(memories),
                "peak": max(memories),
            },
            "quality": {
                "coverage_mean": sum(coverages) / len(coverages),
                "factuality_mean": sum(factualities) / len(factualities),
            },
            "errors": {
                "total_errors": sum(m.error_count for m in metrics_list),
                "total_retries": sum(m.retry_count for m in metrics_list),
                "partial_completions": sum(1 for m in metrics_list if m.partial_completion),
            },
        }

        return stats

    def generate_report(self, agent_name: str) -> str:
        """
        성능 리포트 생성

        Args:
            agent_name: 리포트를 생성할 에이전트 이름

        Returns:
            마크다운 리포트
        """
        metrics_list = self.load_all_metrics(agent_name)
        stats = self.compute_statistics(metrics_list)

        if not stats:
            return f"# 성능 리포트: {agent_name}\n\n데이터가 없습니다."

        report_lines = [
            f"# 성능 리포트: {agent_name}",
            "",
            f"**총 실행 횟수**: {stats['total_runs']}",
            "",
            "## 실행 시간",
            f"- 평균: {stats['duration']['mean']:.2f}초",
            f"- 중앙값 (P50): {stats['duration']['p50']:.2f}초",
            f"- P95: {stats['duration']['p95']:.2f}초",
            f"- 최소: {stats['duration']['min']:.2f}초",
            f"- 최대: {stats['duration']['max']:.2f}초",
            "",
            "## 메모리 사용량",
            f"- 평균: {stats['memory']['mean']:.1f} MB",
            f"- 피크: {stats['memory']['peak']:.1f} MB",
            "",
            "## 품질 메트릭",
            f"- 커버리지: {stats['quality']['coverage_mean']:.1%}",
            f"- 정확성: {stats['quality']['factuality_mean']:.1%}",
            "",
            "## 에러 & 재시도",
            f"- 총 에러 수: {stats['errors']['total_errors']}",
            f"- 총 재시도 수: {stats['errors']['total_retries']}",
            f"- 부분 완료: {stats['errors']['partial_completions']}",
            "",
        ]

        return "\n".join(report_lines)


# 사용 예제
if __name__ == "__main__":
    # 단일 실행 모니터링
    monitor = PerformanceMonitor("news_trend_agent", "test-run-123", "AI trends")

    with monitor.track_node("collect"):
        time.sleep(0.5)  # 작업 시뮬레이션

    monitor.record_data_collected(50)

    with monitor.track_node("analyze"):
        time.sleep(0.3)

    monitor.record_quality_metrics(coverage=0.9, factuality=1.0, actionability=0.8)
    monitor.save_metrics()

    # 집계 리포트 생성
    aggregator = MetricsAggregator()
    report = aggregator.generate_report("news_trend_agent")
    print(report)

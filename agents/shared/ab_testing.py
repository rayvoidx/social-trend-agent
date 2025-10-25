"""
에이전트 비교를 위한 A/B 테스팅 프레임워크

서로 다른 에이전트 버전, 프롬프트, 설정을 비교합니다.

주요 기능:
- 다변량 테스팅 (A/B/C/D...)
- 통계적 유의성 검증
- 자동화된 승자 선택
- 실험 추적 및 기록
- 점진적 롤아웃 관리

Example:
    ```python
    # 실험 생성
    experiment = ABExperiment(
        name="prompt_optimization",
        variants={
            "control": PromptVariant("original_prompt"),
            "variant_a": PromptVariant("optimized_prompt_v1"),
            "variant_b": PromptVariant("optimized_prompt_v2")
        }
    )

    # 실험 실행
    for query in test_queries:
        variant = experiment.assign_variant()
        result = run_agent_with_variant(query, variant)
        experiment.record_result(variant.name, result)

    # 결과 분석
    analysis = experiment.analyze()
    print(f"Winner: {analysis.winner}")
    ```
"""
import json
import random
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from datetime import datetime
import logging
import statistics

logger = logging.getLogger(__name__)


class VariantType(str, Enum):
    """변형(Variant) 타입"""
    CONTROL = "control"
    TREATMENT = "treatment"


class ExperimentStatus(str, Enum):
    """실험 상태"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class AgentVariant:
    """
    에이전트 변형(Variant) 정의

    테스트할 특정 설정을 나타냅니다.
    """
    name: str
    variant_type: VariantType
    config: Dict[str, Any]
    traffic_allocation: float = 0.5  # Percentage of traffic (0.0-1.0)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['variant_type'] = self.variant_type.value
        return data


@dataclass
class ExperimentResult:
    """변형 실행의 단일 결과"""
    variant_name: str
    query: str
    execution_time: float
    quality_score: float
    metrics: Dict[str, Any]
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VariantStatistics:
    """변형에 대한 통계 요약"""
    variant_name: str
    sample_size: int
    mean_quality: float
    std_quality: float
    mean_execution_time: float
    std_execution_time: float
    success_rate: float
    confidence_interval_95: tuple[float, float] = field(default=(0.0, 0.0))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentAnalysis:
    """실험 분석 결과"""
    experiment_name: str
    total_samples: int
    variant_stats: Dict[str, VariantStatistics]
    winner: Optional[str]
    confidence_level: float
    p_value: float
    is_significant: bool
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['variant_stats'] = {
            name: stats.to_dict()
            for name, stats in self.variant_stats.items()
        }
        return data


class ABExperiment:
    """
    A/B 테스팅 실험

    트래픽 할당 및 통계 분석을 통한 다변량 테스팅을 관리합니다.
    """

    def __init__(
        self,
        name: str,
        variants: Dict[str, AgentVariant],
        description: str = "",
        min_sample_size: int = 30,
        confidence_threshold: float = 0.95
    ):
        """
        실험 초기화

        Args:
            name: 실험 이름
            variants: variant_name -> AgentVariant 딕셔너리
            description: 실험 설명
            min_sample_size: 분석 전 변형당 최소 샘플 수
            confidence_threshold: 통계적 유의성을 위한 신뢰 수준
        """
        self.name = name
        self.variants = variants
        self.description = description
        self.min_sample_size = min_sample_size
        self.confidence_threshold = confidence_threshold

        self.status = ExperimentStatus.DRAFT
        self.results: List[ExperimentResult] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        # Normalize traffic allocation
        self._normalize_traffic_allocation()

    def _normalize_traffic_allocation(self):
        """Normalize traffic allocation to sum to 1.0"""
        total = sum(v.traffic_allocation for v in self.variants.values())
        for variant in self.variants.values():
            variant.traffic_allocation /= total

    def start(self):
        """Start experiment"""
        self.status = ExperimentStatus.RUNNING
        self.start_time = datetime.now().timestamp()
        logger.info(f"Experiment '{self.name}' started with {len(self.variants)} variants")

    def stop(self):
        """Stop experiment"""
        self.status = ExperimentStatus.COMPLETED
        self.end_time = datetime.now().timestamp()
        logger.info(f"Experiment '{self.name}' stopped")

    def assign_variant(self) -> AgentVariant:
        """
        Assign a variant based on traffic allocation

        Uses weighted random selection.

        Returns:
            Selected AgentVariant
        """
        # Get variant names and weights
        names = list(self.variants.keys())
        weights = [self.variants[name].traffic_allocation for name in names]

        # Random selection
        selected_name = random.choices(names, weights=weights, k=1)[0]

        return self.variants[selected_name]

    def record_result(
        self,
        variant_name: str,
        query: str,
        execution_time: float,
        quality_score: float,
        metrics: Dict[str, Any]
    ):
        """
        Record experiment result

        Args:
            variant_name: Name of variant that produced this result
            query: Query that was processed
            execution_time: Execution time in seconds
            quality_score: Quality score (0.0-1.0)
            metrics: Additional metrics
        """
        result = ExperimentResult(
            variant_name=variant_name,
            query=query,
            execution_time=execution_time,
            quality_score=quality_score,
            metrics=metrics,
            timestamp=datetime.now().timestamp()
        )

        self.results.append(result)

    def get_variant_results(self, variant_name: str) -> List[ExperimentResult]:
        """Get all results for a specific variant"""
        return [r for r in self.results if r.variant_name == variant_name]

    def compute_variant_statistics(self, variant_name: str) -> Optional[VariantStatistics]:
        """
        Compute statistics for a variant

        Args:
            variant_name: Variant name

        Returns:
            VariantStatistics or None if insufficient data
        """
        results = self.get_variant_results(variant_name)

        if not results:
            return None

        quality_scores = [r.quality_score for r in results]
        execution_times = [r.execution_time for r in results]
        successful = [r for r in results if r.quality_score > 0.6]

        mean_quality = statistics.mean(quality_scores)
        std_quality = statistics.stdev(quality_scores) if len(quality_scores) > 1 else 0.0

        # Compute 95% confidence interval for quality
        if len(quality_scores) > 1:
            import math
            margin = 1.96 * (std_quality / math.sqrt(len(quality_scores)))
            ci_95 = (mean_quality - margin, mean_quality + margin)
        else:
            ci_95 = (mean_quality, mean_quality)

        return VariantStatistics(
            variant_name=variant_name,
            sample_size=len(results),
            mean_quality=mean_quality,
            std_quality=std_quality,
            mean_execution_time=statistics.mean(execution_times),
            std_execution_time=statistics.stdev(execution_times) if len(execution_times) > 1 else 0.0,
            success_rate=len(successful) / len(results),
            confidence_interval_95=ci_95
        )

    def analyze(self) -> ExperimentAnalysis:
        """
        Analyze experiment results

        Performs statistical analysis to determine winner.

        Returns:
            ExperimentAnalysis with winner and significance
        """
        # Compute statistics for each variant
        variant_stats = {}
        for variant_name in self.variants.keys():
            stats = self.compute_variant_statistics(variant_name)
            if stats:
                variant_stats[variant_name] = stats

        if not variant_stats:
            return ExperimentAnalysis(
                experiment_name=self.name,
                total_samples=0,
                variant_stats={},
                winner=None,
                confidence_level=0.0,
                p_value=1.0,
                is_significant=False,
                recommendations=["No data collected yet"]
            )

        # Find winner (highest mean quality)
        winner = max(variant_stats.items(), key=lambda x: x[1].mean_quality)
        winner_name = winner[0]
        winner_stats = winner[1]

        # Check statistical significance
        # For simplicity, check if confidence intervals overlap
        is_significant = self._check_significance(variant_stats, winner_name)

        # Compute p-value (simplified)
        p_value = self._compute_p_value(variant_stats, winner_name)

        # Generate recommendations
        recommendations = self._generate_recommendations(variant_stats, winner_name, is_significant)

        return ExperimentAnalysis(
            experiment_name=self.name,
            total_samples=sum(s.sample_size for s in variant_stats.values()),
            variant_stats=variant_stats,
            winner=winner_name if is_significant else None,
            confidence_level=self.confidence_threshold,
            p_value=p_value,
            is_significant=is_significant,
            recommendations=recommendations
        )

    def _check_significance(self, variant_stats: Dict[str, VariantStatistics], winner_name: str) -> bool:
        """
        Check if winner is statistically significant

        Returns True if winner's confidence interval doesn't overlap with others.
        """
        if len(variant_stats) < 2:
            return False

        winner_stats = variant_stats[winner_name]
        winner_ci = winner_stats.confidence_interval_95

        # Check minimum sample size
        if winner_stats.sample_size < self.min_sample_size:
            return False

        # Check if winner is significantly better than all others
        for name, stats in variant_stats.items():
            if name == winner_name:
                continue

            if stats.sample_size < self.min_sample_size:
                continue

            # Check if confidence intervals overlap
            other_ci = stats.confidence_interval_95
            if not (winner_ci[0] > other_ci[1] or winner_ci[1] < other_ci[0]):
                # Intervals overlap - not significant
                return False

        return True

    def _compute_p_value(self, variant_stats: Dict[str, VariantStatistics], winner_name: str) -> float:
        """
        Compute p-value (simplified)

        In production, use scipy.stats.ttest_ind for proper t-test.
        """
        # Simplified p-value calculation
        # In reality, would use proper statistical test (t-test)
        if len(variant_stats) < 2:
            return 1.0

        winner_stats = variant_stats[winner_name]
        other_stats = [s for n, s in variant_stats.items() if n != winner_name]

        # Simplified: based on difference in means relative to standard errors
        max_other_quality = max(s.mean_quality for s in other_stats)
        diff = winner_stats.mean_quality - max_other_quality

        # Rough approximation
        if diff > 0.1:
            return 0.01  # Very significant
        elif diff > 0.05:
            return 0.05  # Significant
        else:
            return 0.15  # Not significant

    def _generate_recommendations(
        self,
        variant_stats: Dict[str, VariantStatistics],
        winner_name: str,
        is_significant: bool
    ) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []

        winner_stats = variant_stats[winner_name]

        if is_significant:
            quality_improvement = (winner_stats.mean_quality -
                                  min(s.mean_quality for s in variant_stats.values())) * 100
            recommendations.append(
                f"Deploy '{winner_name}' variant - shows {quality_improvement:.1f}% quality improvement"
            )
            recommendations.append(f"Gradually rollout to 100% of traffic")
        else:
            recommendations.append("Continue collecting data - no statistically significant winner yet")

            # Check sample sizes
            min_samples = min(s.sample_size for s in variant_stats.values())
            if min_samples < self.min_sample_size:
                recommendations.append(
                    f"Collect at least {self.min_sample_size} samples per variant "
                    f"(currently: {min_samples})"
                )

        # Performance recommendations
        fastest = min(variant_stats.items(), key=lambda x: x[1].mean_execution_time)
        if fastest[0] != winner_name:
            recommendations.append(
                f"Consider '{fastest[0]}' for performance "
                f"({fastest[1].mean_execution_time:.2f}s vs {winner_stats.mean_execution_time:.2f}s)"
            )

        return recommendations

    def save(self, filepath: str):
        """Save experiment to file"""
        data = {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "variants": {name: v.to_dict() for name, v in self.variants.items()},
            "results": [r.to_dict() for r in self.results],
            "start_time": self.start_time,
            "end_time": self.end_time,
            "min_sample_size": self.min_sample_size,
            "confidence_threshold": self.confidence_threshold
        }

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Experiment saved to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> 'ABExperiment':
        """Load experiment from file"""
        with open(filepath) as f:
            data = json.load(f)

        # Reconstruct variants
        variants = {}
        for name, variant_data in data["variants"].items():
            variants[name] = AgentVariant(
                name=variant_data["name"],
                variant_type=VariantType(variant_data["variant_type"]),
                config=variant_data["config"],
                traffic_allocation=variant_data["traffic_allocation"],
                description=variant_data.get("description", "")
            )

        # Create experiment
        experiment = cls(
            name=data["name"],
            variants=variants,
            description=data.get("description", ""),
            min_sample_size=data.get("min_sample_size", 30),
            confidence_threshold=data.get("confidence_threshold", 0.95)
        )

        # Restore state
        experiment.status = ExperimentStatus(data["status"])
        experiment.start_time = data.get("start_time")
        experiment.end_time = data.get("end_time")

        # Restore results
        for result_data in data.get("results", []):
            experiment.results.append(ExperimentResult(**result_data))

        logger.info(f"Experiment loaded from {filepath}")

        return experiment


# Example usage
if __name__ == "__main__":
    # Create experiment
    experiment = ABExperiment(
        name="prompt_optimization_test",
        variants={
            "control": AgentVariant(
                name="control",
                variant_type=VariantType.CONTROL,
                config={"system_prompt": "original"},
                traffic_allocation=0.4
            ),
            "variant_a": AgentVariant(
                name="variant_a",
                variant_type=VariantType.TREATMENT,
                config={"system_prompt": "optimized_v1"},
                traffic_allocation=0.3
            ),
            "variant_b": AgentVariant(
                name="variant_b",
                variant_type=VariantType.TREATMENT,
                config={"system_prompt": "optimized_v2"},
                traffic_allocation=0.3
            )
        },
        description="Testing different system prompts for quality improvement"
    )

    # Start experiment
    experiment.start()

    # Simulate results
    test_queries = ["AI trends", "electric vehicles", "cloud computing"] * 15

    for query in test_queries:
        # Assign variant
        variant = experiment.assign_variant()

        # Simulate execution (in practice, run actual agent)
        execution_time = random.uniform(2.0, 5.0)

        # Simulate quality scores (variant_b is slightly better)
        if variant.name == "variant_b":
            quality = random.gauss(0.85, 0.05)
        elif variant.name == "variant_a":
            quality = random.gauss(0.80, 0.05)
        else:
            quality = random.gauss(0.75, 0.05)

        quality = max(0.0, min(1.0, quality))

        # Record result
        experiment.record_result(
            variant_name=variant.name,
            query=query,
            execution_time=execution_time,
            quality_score=quality,
            metrics={"coverage": quality * 0.9, "factuality": quality * 0.95}
        )

    # Analyze
    analysis = experiment.analyze()

    print(f"\n=== Experiment: {experiment.name} ===")
    print(f"Total samples: {analysis.total_samples}")
    print(f"\nVariant Statistics:")
    for name, stats in analysis.variant_stats.items():
        print(f"\n{name}:")
        print(f"  Samples: {stats.sample_size}")
        print(f"  Quality: {stats.mean_quality:.3f} ± {stats.std_quality:.3f}")
        print(f"  95% CI: ({stats.confidence_interval_95[0]:.3f}, {stats.confidence_interval_95[1]:.3f})")
        print(f"  Execution time: {stats.mean_execution_time:.2f}s")

    print(f"\nWinner: {analysis.winner}")
    print(f"P-value: {analysis.p_value:.4f}")
    print(f"Is significant: {analysis.is_significant}")
    print(f"\nRecommendations:")
    for rec in analysis.recommendations:
        print(f"  - {rec}")

    # Save experiment
    experiment.save("artifacts/experiments/prompt_optimization_test.json")

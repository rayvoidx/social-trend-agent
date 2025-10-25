"""
에이전트 품질을 위한 자동화된 평가 파이프라인

다양한 메트릭을 사용하여 에이전트 출력을 평가합니다:
- 관련성(Relevance): 출력이 쿼리와 얼마나 관련이 있는가
- 완전성(Completeness): 출력이 모든 측면을 다루는가
- 정확성(Accuracy): 정보가 정확한가
- 실행 가능성(Actionability): 권고사항이 실행 가능한가

LangChain 평가 패턴 기반:
https://python.langchain.com/docs/guides/productionization/evaluation/
"""
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EvaluationLevel(str, Enum):
    """평가 품질 레벨"""
    EXCELLENT = "excellent"      # 90-100%
    GOOD = "good"               # 75-89%
    ACCEPTABLE = "acceptable"   # 60-74%
    POOR = "poor"              # 40-59%
    FAILING = "failing"        # 0-39%


@dataclass
class EvaluationMetrics:
    """에이전트 출력에 대한 평가 메트릭"""
    run_id: str
    query: str

    # 핵심 메트릭 (0.0-1.0)
    relevance: float
    completeness: float
    accuracy: float
    actionability: float

    # 종합 점수
    overall_score: float
    level: EvaluationLevel

    # 상세 피드백
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data['level'] = self.level.value
        return data


class AgentEvaluator:
    """
    자동화된 에이전트 평가

    규칙 기반 및 LLM 기반 평가 방법을 사용합니다.
    """

    def __init__(self, use_llm: bool = False):
        """
        평가기 초기화

        Args:
            use_llm: 평가에 LLM 사용 (더 정확하지만 느림)
        """
        self.use_llm = use_llm

    def evaluate_relevance(self, query: str, output: Dict[str, Any]) -> float:
        """
        출력의 쿼리 관련성 평가

        규칙 기반: 쿼리 키워드가 출력에 나타나는지 확인

        Args:
            query: 원본 쿼리
            output: 에이전트 출력 (report_md, analysis 등)

        Returns:
            관련성 점수 (0.0-1.0)
        """
        report_md = output.get("report_md", "")

        # 쿼리에서 키워드 추출
        query_keywords = set(query.lower().split())

        # 리포트에서 키워드 매칭 개수 세기
        report_lower = report_md.lower()
        matches = sum(1 for kw in query_keywords if kw in report_lower)

        # 관련성 계산
        relevance = min(matches / max(len(query_keywords), 1), 1.0)

        return relevance

    def evaluate_completeness(self, output: Dict[str, Any]) -> float:
        """
        출력의 완전성 평가

        모든 필수 섹션이 존재하는지 확인합니다.

        Args:
            output: 에이전트 출력

        Returns:
            완전성 점수 (0.0-1.0)
        """
        report_md = output.get("report_md", "")
        analysis = output.get("analysis", {})

        required_sections = [
            "감성 분석",      # 감성 분석
            "핵심 키워드",    # 키워드
            "주요 인사이트",  # 인사이트
        ]

        # 리포트 섹션 확인
        section_score = sum(1 for section in required_sections if section in report_md) / len(required_sections)

        # 분석 컴포넌트 확인
        has_sentiment = bool(analysis.get("sentiment"))
        has_keywords = bool(analysis.get("keywords"))
        has_summary = bool(analysis.get("summary"))

        analysis_score = sum([has_sentiment, has_keywords, has_summary]) / 3

        # 종합 점수
        completeness = (section_score + analysis_score) / 2

        return completeness

    def evaluate_accuracy(self, output: Dict[str, Any]) -> float:
        """
        출력의 정확성 평가

        규칙 기반: 데이터 품질 지표 확인

        Args:
            output: 에이전트 출력

        Returns:
            정확성 점수 (0.0-1.0)
        """
        metrics = output.get("metrics", {})
        normalized = output.get("normalized", [])

        # 사실성 확인 (모든 항목에 URL이 있는지)
        factuality = metrics.get("factuality", 0.0)

        # 데이터 품질 확인
        has_valid_data = len(normalized) > 0
        all_have_titles = all(item.get("title") for item in normalized) if has_valid_data else False
        all_have_sources = all(item.get("source") for item in normalized) if has_valid_data else False

        data_quality = sum([has_valid_data, all_have_titles, all_have_sources]) / 3

        # 종합 정확성
        accuracy = (factuality + data_quality) / 2

        return accuracy

    def evaluate_actionability(self, output: Dict[str, Any]) -> float:
        """
        권고사항의 실행 가능성 평가

        출력에 실행 가능한 인사이트가 포함되어 있는지 확인합니다.

        Args:
            output: 에이전트 출력

        Returns:
            실행 가능성 점수 (0.0-1.0)
        """
        report_md = output.get("report_md", "")
        analysis = output.get("analysis", {})

        # 실행 지향 키워드 확인
        action_keywords = ["권고", "제안", "추천", "실행", "전략", "개선"]
        action_count = sum(1 for kw in action_keywords if kw in report_md)

        # 권고사항이 있는 요약 확인
        summary = analysis.get("summary", "")
        has_recommendations = any(kw in summary for kw in action_keywords)

        # 점수 계산
        keyword_score = min(action_count / len(action_keywords), 1.0)
        recommendation_score = 1.0 if has_recommendations else 0.0

        actionability = (keyword_score + recommendation_score) / 2

        return actionability

    def evaluate(self, query: str, output: Dict[str, Any]) -> EvaluationMetrics:
        """
        에이전트 출력에 대한 종합 평가

        Args:
            query: 원본 쿼리
            output: report_md, analysis, metrics 등을 포함하는 에이전트 출력

        Returns:
            점수와 피드백이 포함된 EvaluationMetrics
        """
        # 개별 메트릭 계산
        relevance = self.evaluate_relevance(query, output)
        completeness = self.evaluate_completeness(output)
        accuracy = self.evaluate_accuracy(output)
        actionability = self.evaluate_actionability(output)

        # 전체 점수 계산 (가중 평균)
        weights = {
            "relevance": 0.3,
            "completeness": 0.25,
            "accuracy": 0.25,
            "actionability": 0.2
        }

        overall_score = (
            relevance * weights["relevance"] +
            completeness * weights["completeness"] +
            accuracy * weights["accuracy"] +
            actionability * weights["actionability"]
        )

        # 레벨 결정
        if overall_score >= 0.9:
            level = EvaluationLevel.EXCELLENT
        elif overall_score >= 0.75:
            level = EvaluationLevel.GOOD
        elif overall_score >= 0.6:
            level = EvaluationLevel.ACCEPTABLE
        elif overall_score >= 0.4:
            level = EvaluationLevel.POOR
        else:
            level = EvaluationLevel.FAILING

        # 피드백 생성
        strengths, weaknesses, recommendations = self._generate_feedback(
            relevance, completeness, accuracy, actionability
        )

        metrics = EvaluationMetrics(
            run_id=output.get("run_id", "unknown"),
            query=query,
            relevance=relevance,
            completeness=completeness,
            accuracy=accuracy,
            actionability=actionability,
            overall_score=overall_score,
            level=level,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations
        )

        logger.info(
            f"Evaluation complete: score={overall_score:.2f}, level={level.value}"
        )

        return metrics

    def _generate_feedback(
        self,
        relevance: float,
        completeness: float,
        accuracy: float,
        actionability: float
    ) -> tuple[List[str], List[str], List[str]]:
        """
        상세 피드백 생성

        Returns:
            (강점, 약점, 권고사항)
        """
        strengths = []
        weaknesses = []
        recommendations = []

        # 관련성 피드백
        if relevance >= 0.8:
            strengths.append("출력이 쿼리와 매우 관련성이 높습니다")
        elif relevance < 0.5:
            weaknesses.append("출력이 쿼리와의 관련성이 부족합니다")
            recommendations.append("분석에서 쿼리 키워드를 더 두드러지게 포함하세요")

        # 완전성 피드백
        if completeness >= 0.8:
            strengths.append("분석이 포괄적이고 완전합니다")
        elif completeness < 0.5:
            weaknesses.append("분석에 주요 섹션이 누락되어 있습니다")
            recommendations.append("모든 필수 섹션을 포함하세요: 감성, 키워드, 인사이트")

        # 정확성 피드백
        if accuracy >= 0.8:
            strengths.append("데이터 품질과 사실성이 높습니다")
        elif accuracy < 0.5:
            weaknesses.append("데이터 품질 개선이 필요합니다")
            recommendations.append("모든 데이터 소스를 검증하고 사실적인 URL을 보장하세요")

        # 실행 가능성 피드백
        if actionability >= 0.8:
            strengths.append("권고사항이 명확하고 실행 가능합니다")
        elif actionability < 0.5:
            weaknesses.append("권고사항의 실행 가능성이 부족합니다")
            recommendations.append("구체적이고 실행 가능한 권고사항을 제공하세요")

        return strengths, weaknesses, recommendations


class EvaluationPipeline:
    """
    자동화된 평가 파이프라인

    에이전트 출력에 대한 평가를 실행하고 리포트를 생성합니다.
    """

    def __init__(self, evaluator: Optional[AgentEvaluator] = None):
        """
        평가 파이프라인 초기화

        Args:
            evaluator: AgentEvaluator 인스턴스 (None이면 기본값 생성)
        """
        self.evaluator = evaluator or AgentEvaluator()
        self.results: List[EvaluationMetrics] = []

    def evaluate_run(self, query: str, output: Dict[str, Any]) -> EvaluationMetrics:
        """
        단일 에이전트 실행 평가

        Args:
            query: 원본 쿼리
            output: 에이전트 출력

        Returns:
            EvaluationMetrics
        """
        metrics = self.evaluator.evaluate(query, output)
        self.results.append(metrics)
        return metrics

    def evaluate_batch(
        self,
        test_cases: List[Dict[str, Any]]
    ) -> List[EvaluationMetrics]:
        """
        여러 테스트 케이스 평가

        Args:
            test_cases: {query, output} 딕셔너리 리스트

        Returns:
            EvaluationMetrics 리스트
        """
        results = []
        for test_case in test_cases:
            query = test_case["query"]
            output = test_case["output"]
            metrics = self.evaluate_run(query, output)
            results.append(metrics)

        return results

    def generate_summary_report(self) -> str:
        """
        모든 평가에 대한 요약 리포트 생성

        Returns:
            마크다운 리포트
        """
        if not self.results:
            return "# 평가 요약\n\n아직 평가가 없습니다."

        # 집계 통계 계산
        avg_relevance = sum(m.relevance for m in self.results) / len(self.results)
        avg_completeness = sum(m.completeness for m in self.results) / len(self.results)
        avg_accuracy = sum(m.accuracy for m in self.results) / len(self.results)
        avg_actionability = sum(m.actionability for m in self.results) / len(self.results)
        avg_overall = sum(m.overall_score for m in self.results) / len(self.results)

        # 레벨별 개수
        level_counts = {}
        for level in EvaluationLevel:
            level_counts[level.value] = sum(1 for m in self.results if m.level == level)

        report_lines = [
            f"# 평가 요약",
            f"",
            f"**총 평가 수**: {len(self.results)}",
            f"",
            f"## 평균 점수",
            f"- 관련성: {avg_relevance:.1%}",
            f"- 완전성: {avg_completeness:.1%}",
            f"- 정확성: {avg_accuracy:.1%}",
            f"- 실행 가능성: {avg_actionability:.1%}",
            f"- **전체**: {avg_overall:.1%}",
            f"",
            f"## 품질 분포",
        ]

        for level in EvaluationLevel:
            count = level_counts[level.value]
            pct = (count / len(self.results)) * 100
            report_lines.append(f"- {level.value.capitalize()}: {count}개 ({pct:.1f}%)")

        report_lines.extend([
            f"",
            f"## 공통 강점",
        ])

        # 강점 집계
        all_strengths = []
        for m in self.results:
            all_strengths.extend(m.strengths)

        strength_counts = {}
        for strength in all_strengths:
            strength_counts[strength] = strength_counts.get(strength, 0) + 1

        for strength, count in sorted(strength_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            report_lines.append(f"- {strength} ({count}회 발생)")

        report_lines.extend([
            f"",
            f"## 공통 약점",
        ])

        # 약점 집계
        all_weaknesses = []
        for m in self.results:
            all_weaknesses.extend(m.weaknesses)

        weakness_counts = {}
        for weakness in all_weaknesses:
            weakness_counts[weakness] = weakness_counts.get(weakness, 0) + 1

        for weakness, count in sorted(weakness_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            report_lines.append(f"- {weakness} ({count}회 발생)")

        return "\n".join(report_lines)

    def save_results(self, filepath: str):
        """
        평가 결과를 JSON으로 저장

        Args:
            filepath: 저장할 경로
        """
        with open(filepath, "w") as f:
            data = [m.to_dict() for m in self.results]
            json.dump(data, f, indent=2)

        logger.info(f"Evaluation results saved to {filepath}")


# 사용 예제
if __name__ == "__main__":
    # 단일 평가
    evaluator = AgentEvaluator()

    test_output = {
        "run_id": "test-123",
        "query": "AI trends",
        "report_md": "# AI Trends\n\n## 감성 분석\n긍정적...\n\n## 핵심 키워드\n- AI\n- machine learning\n\n## 주요 인사이트\n권고사항...",
        "analysis": {
            "sentiment": {"positive": 10, "neutral": 5, "negative": 2},
            "keywords": {"top_keywords": [{"keyword": "AI", "count": 15}]},
            "summary": "AI에 대한 긍정적 반응. 마케팅 전략 권고..."
        },
        "metrics": {"coverage": 0.9, "factuality": 1.0, "actionability": 0.8},
        "normalized": [
            {"title": "AI News", "url": "https://example.com", "source": "Test"}
        ]
    }

    metrics = evaluator.evaluate("AI trends", test_output)
    print(f"전체 점수: {metrics.overall_score:.2f}")
    print(f"레벨: {metrics.level.value}")
    print(f"강점: {metrics.strengths}")
    print(f"약점: {metrics.weaknesses}")

    # 배치 평가
    pipeline = EvaluationPipeline(evaluator)
    pipeline.evaluate_run("AI trends", test_output)
    report = pipeline.generate_summary_report()
    print(report)

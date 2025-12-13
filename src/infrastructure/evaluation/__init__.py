"""
Agent evaluation module.

Provides tools for evaluating agent outputs and measuring quality metrics.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class QualityLevel(Enum):
    """Quality level classification."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass
class EvaluationMetrics:
    """Metrics from agent evaluation."""

    relevance: float = 0.0
    completeness: float = 0.0
    accuracy: float = 0.0
    actionability: float = 0.0
    overall_score: float = 0.0
    level: QualityLevel = QualityLevel.FAIR
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class AgentEvaluator:
    """
    Evaluates agent outputs for quality and completeness.

    This evaluator assesses various aspects of agent output including:
    - Relevance to the query
    - Completeness of analysis
    - Accuracy of information
    - Actionability of recommendations
    """

    def __init__(self):
        """Initialize the evaluator."""
        pass

    def evaluate(self, query: str, output: Dict[str, Any]) -> EvaluationMetrics:
        """
        Evaluate agent output against the query.

        Args:
            query: Original query
            output: Agent output dictionary containing report_md, analysis, metrics, etc.

        Returns:
            EvaluationMetrics with scores and feedback
        """
        # Extract components
        report = output.get("report_md", "")
        analysis = output.get("analysis", {})
        metrics = output.get("metrics", {})
        normalized = output.get("normalized", [])

        # Calculate scores
        relevance = self._score_relevance(query, report, analysis)
        completeness = self._score_completeness(report, analysis, normalized)
        accuracy = self._score_accuracy(metrics)
        actionability = self._score_actionability(report, analysis)

        # Calculate overall score
        overall = (relevance + completeness + accuracy + actionability) / 4

        # Determine level
        if overall >= 0.85:
            level = QualityLevel.EXCELLENT
        elif overall >= 0.70:
            level = QualityLevel.GOOD
        elif overall >= 0.50:
            level = QualityLevel.FAIR
        else:
            level = QualityLevel.POOR

        # Generate feedback
        strengths = self._identify_strengths(relevance, completeness, accuracy, actionability)
        weaknesses = self._identify_weaknesses(relevance, completeness, accuracy, actionability)
        recommendations = self._generate_recommendations(weaknesses)

        return EvaluationMetrics(
            relevance=relevance,
            completeness=completeness,
            accuracy=accuracy,
            actionability=actionability,
            overall_score=overall,
            level=level,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
        )

    def _score_relevance(self, query: str, report: str, analysis: Dict) -> float:
        """Score relevance of output to query."""
        if not report:
            return 0.0

        # Check if query terms appear in report
        query_terms = query.lower().split()
        report_lower = report.lower()

        matches = sum(1 for term in query_terms if term in report_lower)
        term_score = matches / len(query_terms) if query_terms else 0.5

        # Check if analysis has content
        analysis_score = 0.5 if analysis else 0.0

        return min(1.0, (term_score + analysis_score) / 1.5)

    def _score_completeness(self, report: str, analysis: Dict, normalized: List) -> float:
        """Score completeness of analysis."""
        score = 0.0

        # Has report
        if report and len(report) > 100:
            score += 0.3

        # Has sentiment analysis
        if analysis.get("sentiment"):
            score += 0.2

        # Has keywords
        if analysis.get("keywords"):
            score += 0.2

        # Has summary
        if analysis.get("summary"):
            score += 0.15

        # Has normalized data
        if normalized and len(normalized) > 0:
            score += 0.15

        return min(1.0, score)

    def _score_accuracy(self, metrics: Dict) -> float:
        """Score accuracy based on metrics."""
        if not metrics:
            return 0.5

        coverage = metrics.get("coverage", 0.5)
        factuality = metrics.get("factuality", 0.5)

        return (coverage + factuality) / 2

    def _score_actionability(self, report: str, analysis: Dict) -> float:
        """Score actionability of recommendations."""
        score = 0.0

        # Check for actionable keywords in report
        actionable_terms = [
            "recommend",
            "suggest",
            "action",
            "should",
            "consider",
            "권고",
            "추천",
            "제안",
        ]
        report_lower = report.lower() if report else ""

        for term in actionable_terms:
            if term in report_lower:
                score += 0.15

        # Check for insights in analysis
        if analysis.get("llm_insights"):
            score += 0.2

        return min(1.0, score)

    def _identify_strengths(
        self, relevance: float, completeness: float, accuracy: float, actionability: float
    ) -> List[str]:
        """Identify strengths based on scores."""
        strengths = []

        if relevance >= 0.8:
            strengths.append("Highly relevant to query")
        if completeness >= 0.8:
            strengths.append("Comprehensive analysis")
        if accuracy >= 0.8:
            strengths.append("Accurate and factual")
        if actionability >= 0.8:
            strengths.append("Clear actionable recommendations")

        return strengths if strengths else ["Basic analysis provided"]

    def _identify_weaknesses(
        self, relevance: float, completeness: float, accuracy: float, actionability: float
    ) -> List[str]:
        """Identify weaknesses based on scores."""
        weaknesses = []

        if relevance < 0.5:
            weaknesses.append("Low relevance to query")
        if completeness < 0.5:
            weaknesses.append("Incomplete analysis")
        if accuracy < 0.5:
            weaknesses.append("Accuracy concerns")
        if actionability < 0.5:
            weaknesses.append("Lacks actionable recommendations")

        return weaknesses

    def _generate_recommendations(self, weaknesses: List[str]) -> List[str]:
        """Generate recommendations based on weaknesses."""
        recommendations = []

        for weakness in weaknesses:
            if "relevance" in weakness.lower():
                recommendations.append("Include more query-specific content")
            if "incomplete" in weakness.lower():
                recommendations.append("Add sentiment analysis, keywords, and summary")
            if "accuracy" in weakness.lower():
                recommendations.append("Verify data sources and increase coverage")
            if "actionable" in weakness.lower():
                recommendations.append("Add specific recommendations and next steps")

        return recommendations if recommendations else ["Continue current approach"]


__all__ = ["AgentEvaluator", "EvaluationMetrics", "QualityLevel"]

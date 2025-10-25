"""
Integration tests for News Trend Agent

Tests complete end-to-end workflows including:
- Full pipeline execution
- Advanced features (conditional edges, streaming)
- Performance monitoring
- Evaluation
"""
import pytest
import asyncio
from agents.news_trend_agent.graph import run_agent
from agents.news_trend_agent.graph_advanced import (
    run_agent_advanced,
    run_agent_with_streaming
)
from agents.shared.monitoring import PerformanceMonitor
from agents.shared.evaluation import AgentEvaluator


class TestBasicPipeline:
    """Test basic agent pipeline"""

    def test_full_pipeline_execution(self):
        """Test complete pipeline from query to report"""
        # Run agent
        final_state = run_agent(
            query="AI trends",
            time_window="7d",
            language="en",
            max_results=5
        )

        # Verify state
        assert final_state.query == "AI trends"
        assert len(final_state.raw_items) > 0
        assert len(final_state.normalized) > 0
        assert final_state.analysis is not None
        assert final_state.report_md is not None
        assert final_state.metrics is not None

        # Verify analysis components
        assert "sentiment" in final_state.analysis
        assert "keywords" in final_state.analysis
        assert "summary" in final_state.analysis

        # Verify metrics
        assert "coverage" in final_state.metrics
        assert "factuality" in final_state.metrics
        assert "actionability" in final_state.metrics

    def test_korean_language_support(self):
        """Test Korean language processing"""
        final_state = run_agent(
            query="전기차",
            time_window="7d",
            language="ko",
            max_results=5
        )

        # Verify Korean content in report
        assert "전기차" in final_state.report_md or "전기차" in str(final_state.normalized)
        assert final_state.language == "ko"

    def test_different_time_windows(self):
        """Test different time window configurations"""
        time_windows = ["24h", "7d", "30d"]

        for tw in time_windows:
            final_state = run_agent(
                query="test",
                time_window=tw,
                max_results=3
            )

            assert final_state.time_window == tw
            assert final_state.report_md is not None


class TestAdvancedFeatures:
    """Test advanced agent features"""

    def test_advanced_pipeline_with_conditional_edges(self):
        """Test advanced pipeline with error recovery"""
        final_state = run_agent_advanced(
            query="AI trends",
            time_window="7d",
            max_results=5
        )

        # Should complete successfully even with potential errors
        assert final_state is not None
        assert final_state.report_md is not None

    @pytest.mark.asyncio
    async def test_streaming_execution(self):
        """Test streaming agent execution"""
        events = []

        async def capture_event(event):
            """Capture streaming events"""
            events.append(event)

        final_state = await run_agent_with_streaming(
            query="AI trends",
            time_window="7d",
            max_results=3,
            stream_callback=capture_event
        )

        # Verify events were emitted
        assert len(events) > 0

        # Verify final state
        assert final_state is not None


class TestPerformanceMonitoring:
    """Test performance monitoring integration"""

    def test_performance_tracking(self):
        """Test performance monitoring during execution"""
        monitor = PerformanceMonitor("news_trend_agent", "test-run", "AI trends")

        # Track collect node
        with monitor.track_node("collect"):
            final_state = run_agent(
                query="AI trends",
                max_results=3
            )

        # Record metrics
        monitor.record_data_collected(len(final_state.raw_items))
        monitor.record_data_normalized(len(final_state.normalized))
        monitor.record_quality_metrics(
            coverage=final_state.metrics.get("coverage", 0.0),
            factuality=final_state.metrics.get("factuality", 0.0),
            actionability=final_state.metrics.get("actionability", 0.0)
        )

        # Finalize
        metrics = monitor.finalize()

        # Verify metrics
        assert metrics.duration_seconds > 0
        assert metrics.items_collected > 0
        assert metrics.node_timings.get("collect", 0) > 0
        assert 0 <= metrics.coverage <= 1.0

    def test_metrics_persistence(self, tmp_path):
        """Test saving and loading metrics"""
        monitor = PerformanceMonitor("news_trend_agent", "test-run", "test query")

        with monitor.track_node("test"):
            pass

        # Save to temporary directory
        filepath = monitor.save_metrics(str(tmp_path))

        # Verify file exists
        assert filepath.exists()

        # Verify JSON is valid
        import json
        with open(filepath) as f:
            data = json.load(f)

        assert data["agent_name"] == "news_trend_agent"
        assert data["run_id"] == "test-run"


class TestEvaluation:
    """Test automated evaluation"""

    def test_evaluation_metrics(self):
        """Test evaluation of agent output"""
        # Run agent
        final_state = run_agent(
            query="AI trends",
            max_results=5
        )

        # Prepare output for evaluation
        output = {
            "run_id": final_state.run_id,
            "report_md": final_state.report_md,
            "analysis": final_state.analysis,
            "metrics": final_state.metrics,
            "normalized": final_state.normalized
        }

        # Evaluate
        evaluator = AgentEvaluator()
        eval_metrics = evaluator.evaluate("AI trends", output)

        # Verify evaluation
        assert 0 <= eval_metrics.relevance <= 1.0
        assert 0 <= eval_metrics.completeness <= 1.0
        assert 0 <= eval_metrics.accuracy <= 1.0
        assert 0 <= eval_metrics.actionability <= 1.0
        assert 0 <= eval_metrics.overall_score <= 1.0

        # Verify feedback
        assert isinstance(eval_metrics.strengths, list)
        assert isinstance(eval_metrics.weaknesses, list)
        assert isinstance(eval_metrics.recommendations, list)

    def test_evaluation_levels(self):
        """Test evaluation level classification"""
        evaluator = AgentEvaluator()

        # Create mock outputs with different quality levels
        high_quality_output = {
            "run_id": "test-1",
            "report_md": "# AI trends\n\n## 감성 분석\nPositive sentiment\n\n## 핵심 키워드\n- AI\n- trends\n\n## 주요 인사이트\nRecommendations: focus on AI strategy",
            "analysis": {
                "sentiment": {"positive": 10},
                "keywords": {"top_keywords": [{"keyword": "AI", "count": 10}]},
                "summary": "Great insights with actionable recommendations"
            },
            "metrics": {"coverage": 0.95, "factuality": 1.0, "actionability": 0.9},
            "normalized": [{"title": "AI", "url": "http://test.com", "source": "Test"}]
        }

        metrics = evaluator.evaluate("AI trends", high_quality_output)

        # Should be excellent or good
        assert metrics.level.value in ["excellent", "good"]
        assert metrics.overall_score >= 0.75


class TestErrorRecovery:
    """Test error handling and recovery"""

    def test_graceful_degradation_no_api_keys(self):
        """Test agent works without API keys (sample data fallback)"""
        import os
        # Temporarily clear API keys
        old_env = os.environ.copy()
        os.environ.pop("NEWS_API_KEY", None)
        os.environ.pop("NAVER_CLIENT_ID", None)

        try:
            final_state = run_agent(
                query="test",
                max_results=3
            )

            # Should still complete with sample data
            assert final_state is not None
            assert len(final_state.raw_items) > 0
            assert final_state.report_md is not None

        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(old_env)

    def test_partial_completion_handling(self):
        """Test handling of partial completions"""
        # Run with very limited results to trigger potential partial completion
        final_state = run_agent(
            query="very specific niche query that might fail",
            max_results=1
        )

        # Should complete even with limited or no data
        assert final_state is not None
        # May have empty results but should not crash


@pytest.fixture
def sample_agent_output():
    """Fixture providing sample agent output for testing"""
    return {
        "run_id": "fixture-test",
        "query": "AI trends",
        "report_md": """# AI Trends Analysis

## 감성 분석
- Positive: 10 (60%)
- Neutral: 5 (30%)
- Negative: 2 (10%)

## 핵심 키워드
- AI
- machine learning
- trends

## 주요 인사이트
AI trends show positive sentiment. Recommended actions:
- Focus on machine learning strategies
- Monitor emerging trends
""",
        "analysis": {
            "sentiment": {
                "positive": 10,
                "neutral": 5,
                "negative": 2,
                "positive_pct": 60.0
            },
            "keywords": {
                "top_keywords": [
                    {"keyword": "AI", "count": 15},
                    {"keyword": "trends", "count": 10}
                ]
            },
            "summary": "Positive trends with actionable recommendations"
        },
        "metrics": {
            "coverage": 0.9,
            "factuality": 1.0,
            "actionability": 0.8
        },
        "normalized": [
            {
                "title": "AI Trends 2024",
                "description": "Latest AI trends",
                "url": "https://example.com/ai-trends",
                "source": "Tech News",
                "published_at": "2024-01-01"
            }
        ]
    }


def test_evaluation_with_fixture(sample_agent_output):
    """Test evaluation using fixture"""
    evaluator = AgentEvaluator()
    metrics = evaluator.evaluate("AI trends", sample_agent_output)

    assert metrics.overall_score > 0.7  # Should be good quality
    assert len(metrics.strengths) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

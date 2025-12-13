"""
Integration tests for News Trend Agent

Tests complete end-to-end workflows including:
- Full pipeline execution
- Advanced features (conditional edges, streaming)
- Performance monitoring
- Evaluation
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from src.agents.news_trend.graph import run_agent
from src.infrastructure.monitoring import track_operation, get_metrics_registry
from src.infrastructure.evaluation import AgentEvaluator


# Sample news data for mocking
SAMPLE_NEWS_DATA = [
    {
        "title": "AI trends in 2024",
        "description": "Latest developments in artificial intelligence",
        "url": "https://example.com/news1",
        "source": {"name": "Tech News"},
        "publishedAt": "2024-11-01T10:00:00Z",
        "content": "AI is transforming industries...",
    },
    {
        "title": "Machine learning advances",
        "description": "New breakthroughs in ML",
        "url": "https://example.com/news2",
        "source": {"name": "Science Daily"},
        "publishedAt": "2024-11-01T11:00:00Z",
        "content": "Researchers have developed...",
    },
]


@pytest.fixture
def mock_llm():
    """Mock LLM for testing"""
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(
        content="AI trends show positive growth. Key insights: increased adoption, new applications emerging."
    )
    # Mock chat_json method if used
    mock.chat_json.return_value = {
        "positive": 10,
        "neutral": 5,
        "negative": 2,
        "key_emotions": ["excitement"],
        "summary": "Positive trends",
    }
    return mock


class TestBasicPipeline:
    """Test basic agent pipeline"""

    def test_full_pipeline_execution(self, mock_llm):
        """Test complete pipeline from query to report"""
        with patch("src.agents.news_trend.graph.search_news", return_value=SAMPLE_NEWS_DATA):
            # Patch get_llm_client to return mock_llm for tools
            with patch("src.integrations.llm.llm_client.get_llm_client", return_value=mock_llm):
                # Also patch _get_llm if used by legacy graph
                with patch("src.agents.news_trend.tools._get_llm", return_value=mock_llm):
                    # Run agent
                    final_state = run_agent(
                        query="AI trends",
                        time_window="7d",
                        language="en",
                        max_results=5,
                        require_approval=False,
                    )

                    # Verify state (NewsAgentState object)
                    # Convert to dict if needed or access attributes
                    if hasattr(final_state, "model_dump"):
                        state_dict = final_state.model_dump()
                    else:
                        state_dict = final_state

                    assert state_dict["query"] == "AI trends"
                    assert len(state_dict["raw_items"]) > 0
                    assert len(state_dict["normalized"]) > 0
                    assert state_dict["analysis"] is not None
                    assert state_dict["report_md"] is not None
                    assert state_dict["metrics"] is not None

                    # Verify analysis components
                    assert "sentiment" in state_dict["analysis"]
                    assert "keywords" in state_dict["analysis"]
                    assert "summary" in state_dict["analysis"]

                    # Verify metrics
                    assert "coverage" in state_dict["metrics"]
                    assert "factuality" in state_dict["metrics"]
                    assert "actionability" in state_dict["metrics"]

    def test_korean_language_support(self, mock_llm):
        """Test Korean language processing"""
        korean_news = [
            {
                "title": "전기차 시장 성장",
                "description": "전기차 판매량이 증가하고 있습니다.",
                "url": "https://example.com/news1",
                "source": {"name": "경제뉴스"},
                "publishedAt": "2024-11-01T10:00:00Z",
                "content": "전기차 관련 내용...",
            }
        ]

        with patch("src.agents.news_trend.graph.search_news", return_value=korean_news):
            with patch("src.integrations.llm.llm_client.get_llm_client", return_value=mock_llm):
                final_state = run_agent(
                    query="전기차",
                    time_window="7d",
                    language="ko",
                    max_results=5,
                    require_approval=False,
                )

                if hasattr(final_state, "model_dump"):
                    state_dict = final_state.model_dump()
                else:
                    state_dict = final_state

                # Verify Korean content in report
                assert "전기차" in state_dict["report_md"] or "전기차" in str(
                    state_dict["normalized"]
                )
                assert state_dict["language"] == "ko"

    def test_different_time_windows(self, mock_llm):
        """Test different time window configurations"""
        time_windows = ["24h", "7d", "30d"]

        with patch("src.agents.news_trend.graph.search_news", return_value=SAMPLE_NEWS_DATA):
            with patch("src.integrations.llm.llm_client.get_llm_client", return_value=mock_llm):
                for tw in time_windows:
                    final_state = run_agent(
                        query="test", time_window=tw, max_results=3, require_approval=False
                    )

                    if hasattr(final_state, "time_window"):
                        assert final_state.time_window == tw
                        assert final_state.report_md is not None
                    else:
                        assert final_state["time_window"] == tw
                        assert final_state["report_md"] is not None


class TestAdvancedFeatures:
    """Test advanced agent features"""

    def test_advanced_pipeline_with_conditional_edges(self, mock_llm):
        """Test advanced pipeline with error recovery"""
        with patch("src.agents.news_trend.graph.search_news", return_value=SAMPLE_NEWS_DATA):
            with patch("src.integrations.llm.llm_client.get_llm_client", return_value=mock_llm):
                try:
                    from src.agents.news_trend.graph_advanced import run_agent_advanced

                    final_state = run_agent_advanced(
                        query="AI trends", time_window="7d", max_results=5
                    )
                    # Should complete successfully even with potential errors
                    assert final_state is not None
                except ImportError:
                    pytest.skip("graph_advanced not available")

    @pytest.mark.asyncio
    async def test_streaming_execution(self, mock_llm):
        """Test streaming agent execution"""
        try:
            from src.agents.news_trend.graph_advanced import run_agent_with_streaming
        except ImportError:
            pytest.skip("graph_advanced not available")

        events = []

        async def capture_event(event):
            """Capture streaming events"""
            events.append(event)

        with patch("src.agents.news_trend.graph.search_news", return_value=SAMPLE_NEWS_DATA):
            with patch("src.integrations.llm.llm_client.get_llm_client", return_value=mock_llm):
                final_state = await run_agent_with_streaming(
                    query="AI trends",
                    time_window="7d",
                    max_results=3,
                    stream_callback=capture_event,
                )

                # Verify events were emitted
                assert len(events) > 0

                # Verify final state
                assert final_state is not None


class TestPerformanceMonitoring:
    """Test performance monitoring integration"""

    def test_performance_tracking(self, mock_llm):
        """Test performance monitoring during execution"""

        with patch("src.agents.news_trend.graph.search_news", return_value=SAMPLE_NEWS_DATA):
            with patch("src.integrations.llm.llm_client.get_llm_client", return_value=mock_llm):
                # Track collect node using the new monitoring system
                with track_operation("collect_test", labels={"agent": "news_trend"}):
                    final_state = run_agent(
                        query="AI trends", max_results=3, require_approval=False
                    )

                # Verify metrics (using get_snapshot)
                registry = get_metrics_registry()
                snapshot = registry.get_snapshot()

                # Check if we have any metrics recorded
                # Note: Exact keys depend on what run_agent records internally
                assert isinstance(snapshot, dict)

                if hasattr(final_state, "metrics"):
                    assert final_state.metrics is not None

    def test_metrics_persistence(self, mock_llm, tmp_path):
        """Test saving and loading metrics (simulated with snapshot)"""

        # Create some metrics
        registry = get_metrics_registry()
        # Ensure registry is initialized

        # Take snapshot
        snapshot = registry.get_snapshot()

        # Save to file
        filepath = tmp_path / "metrics.json"
        with open(filepath, "w") as f:
            json.dump(snapshot, f)

        # Verify file exists
        assert filepath.exists()

        # Verify JSON is valid
        with open(filepath) as f:
            data = json.load(f)

        assert isinstance(data, dict)


class TestEvaluation:
    """Test automated evaluation"""

    def test_evaluation_metrics(self, mock_llm):
        """Test evaluation of agent output"""
        with patch("src.agents.news_trend.graph.search_news", return_value=SAMPLE_NEWS_DATA):
            with patch("src.integrations.llm.llm_client.get_llm_client", return_value=mock_llm):
                # Run agent
                final_state = run_agent(query="AI trends", max_results=5, require_approval=False)

                # Prepare output for evaluation
                if hasattr(final_state, "model_dump"):
                    state_dict = final_state.model_dump()
                else:
                    state_dict = final_state

                output = {
                    "run_id": state_dict.get("run_id"),
                    "report_md": state_dict.get("report_md"),
                    "analysis": state_dict.get("analysis"),
                    "metrics": state_dict.get("metrics"),
                    "normalized": state_dict.get("normalized"),
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
                "summary": "Great insights with actionable recommendations",
            },
            "metrics": {"coverage": 0.95, "factuality": 1.0, "actionability": 0.9},
            "normalized": [{"title": "AI", "url": "http://test.com", "source": "Test"}],
        }

        metrics = evaluator.evaluate("AI trends", high_quality_output)

        # Should be excellent or good
        assert metrics.level.value in ["excellent", "good"]
        assert metrics.overall_score >= 0.75


class TestErrorRecovery:
    """Test error handling and recovery"""

    def test_graceful_degradation_no_api_keys(self, mock_llm):
        """Test agent works without API keys (sample data fallback)"""
        with patch("src.agents.news_trend.graph.search_news", return_value=SAMPLE_NEWS_DATA):
            with patch("src.integrations.llm.llm_client.get_llm_client", return_value=mock_llm):
                final_state = run_agent(query="test", max_results=3, require_approval=False)

                # Should complete with mocked data
                assert final_state is not None
                if hasattr(final_state, "raw_items"):
                    assert len(final_state.raw_items) > 0
                    assert final_state.report_md is not None
                else:
                    assert len(final_state["raw_items"]) > 0
                    assert final_state["report_md"] is not None

    def test_partial_completion_handling(self, mock_llm):
        """Test handling of partial completions"""
        with patch("src.agents.news_trend.graph.search_news", return_value=[]):
            with patch("src.integrations.llm.llm_client.get_llm_client", return_value=mock_llm):
                # Run with empty results
                final_state = run_agent(
                    query="very specific niche query that might fail",
                    max_results=1,
                    require_approval=False,
                )

                # Should complete even with no data
                assert final_state is not None


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
            "sentiment": {"positive": 10, "neutral": 5, "negative": 2, "positive_pct": 60.0},
            "keywords": {
                "top_keywords": [{"keyword": "AI", "count": 15}, {"keyword": "trends", "count": 10}]
            },
            "summary": "Positive trends with actionable recommendations",
        },
        "metrics": {"coverage": 0.9, "factuality": 1.0, "actionability": 0.8},
        "normalized": [
            {
                "title": "AI Trends 2024",
                "description": "Latest AI trends",
                "url": "https://example.com/ai-trends",
                "source": "Tech News",
                "published_at": "2024-01-01",
            }
        ],
    }


def test_evaluation_with_fixture(sample_agent_output):
    """Test evaluation using fixture"""
    evaluator = AgentEvaluator()
    metrics = evaluator.evaluate("AI trends", sample_agent_output)

    assert metrics.overall_score > 0.7  # Should be good quality
    assert len(metrics.strengths) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

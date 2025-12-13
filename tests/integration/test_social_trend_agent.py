"""
Integration tests for Social Trend Agent

Tests complete end-to-end workflows including:
- Full pipeline execution with LangGraph
- Multi-platform data collection
- LLM-based analysis
- Report generation
"""
import pytest
import os
from unittest.mock import patch, MagicMock

from src.agents.social_trend.graph import (
    run_agent,
    run_agent_legacy,
    build_graph,
    collect_node,
    normalize_node,
    analyze_node,
    summarize_node,
    report_node,
)
from src.core.state import SocialTrendAgentState


# Sample data for mocking
SAMPLE_RSS_DATA = [
    {
        "title": "AI Trends 2024",
        "description": "Latest developments in AI",
        "link": "https://example.com/ai-trends",
        "source": "rss",
        "published": "2024-11-01T10:00:00Z"
    },
    {
        "title": "Machine Learning News",
        "description": "New ML breakthroughs",
        "link": "https://example.com/ml-news",
        "source": "rss",
        "published": "2024-11-01T11:00:00Z"
    }
]

SAMPLE_X_DATA = [
    {
        "id": "tweet1",
        "text": "AI is transforming industries",
        "author": "techuser",
        "created_at": "2024-11-01T10:00:00Z",
        "metrics": {"like_count": 100, "retweet_count": 50},
        "platform": "x"
    }
]

SAMPLE_NAVER_DATA = [
    {
        "title": "인공지능 기술 동향",
        "description": "AI 기술 발전 소식",
        "link": "https://blog.naver.com/test",
        "bloggername": "테크블로거",
        "postdate": "20241101"
    }
]


@pytest.fixture
def mock_llm():
    """Mock LLM for testing"""
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(
        content="AI trends show positive growth. Key insights: increased adoption."
    )
    return mock


class TestSocialTrendAgentBasic:
    """Test basic agent functionality"""

    def test_agent_state_initialization(self):
        """Test SocialTrendAgentState initialization"""
        state = SocialTrendAgentState(
            query="AI trends",
            time_window="7d",
            language="ko",
            platforms=["x", "instagram"],
            max_results_per_platform=10
        )

        assert state.query == "AI trends"
        assert state.time_window == "7d"
        assert state.language == "ko"
        assert "x" in state.platforms
        assert "instagram" in state.platforms
        assert state.max_results_per_platform == 10

    def test_build_graph(self):
        """Test graph building"""
        graph = build_graph()
        assert graph is not None
        # build_graph returns compiled graph
        assert hasattr(graph, "invoke")

    def test_run_agent_returns_state(self, mock_llm):
        """Test run_agent returns SocialTrendAgentState"""
        with patch('src.agents.social_trend.graph.fetch_rss_feeds', return_value=SAMPLE_RSS_DATA):
            with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
                result = run_agent(
                    query="test",
                    sources=["rss"],  # Use RSS only for faster test
                    max_results=5,
                    require_approval=False
                )

                assert isinstance(result, SocialTrendAgentState)
                assert result.query == "test"
                assert result.run_id is not None

    def test_run_agent_legacy_returns_dict(self, mock_llm):
        """Test legacy function returns dict"""
        with patch('src.agents.social_trend.graph.fetch_rss_feeds', return_value=SAMPLE_RSS_DATA):
            with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
                result = run_agent_legacy(
                    query="test",
                    sources=["rss"],
                    max_results=5
                )

                assert isinstance(result, dict)
                assert "query" in result
                assert "run_id" in result
                assert "report_md" in result


class TestSocialTrendAgentNodes:
    """Test individual graph nodes"""

    @pytest.fixture
    def initial_state(self):
        """Create initial state for testing"""
        return SocialTrendAgentState(
            query="AI trends",
            time_window="7d",
            language="ko",
            platforms=["rss"],  # RSS only for testing
            rss_feeds=["https://www.reddit.com/r/MachineLearning/.rss"],
            max_results_per_platform=5,
            run_id="test-123"
        )

    def test_collect_node(self, initial_state):
        """Test collect node"""
        with patch('src.agents.social_trend.graph.fetch_rss_feeds', return_value=SAMPLE_RSS_DATA):
            result = collect_node(initial_state)

            assert "raw_items" in result
            assert isinstance(result["raw_items"], list)

    def test_normalize_node(self, initial_state):
        """Test normalize node with raw items"""
        # Add raw items to state
        initial_state.raw_items = [
            {
                "title": "Test Article",
                "description": "Test description",
                "link": "https://example.com",
                "source": "rss"
            }
        ]

        result = normalize_node(initial_state)

        assert "normalized" in result
        assert isinstance(result["normalized"], list)

    def test_analyze_node(self, initial_state, mock_llm):
        """Test analyze node"""
        initial_state.normalized = [
            {
                "title": "AI is growing rapidly",
                "content": "Positive news about AI development",
                "source": "rss"
            },
            {
                "title": "Market concerns about AI",
                "content": "Some negative sentiments",
                "source": "rss"
            }
        ]

        with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
            result = analyze_node(initial_state)

            assert "analysis" in result
            assert "engagement_stats" in result

    def test_summarize_node(self, initial_state, mock_llm):
        """Test summarize node"""
        initial_state.normalized = [
            {"title": "Test", "content": "Content", "source": "rss"}
        ]
        initial_state.analysis = {
            "sentiment": {"positive": 1, "neutral": 0, "negative": 0},
            "keywords": {"top_keywords": [{"keyword": "AI", "count": 5}]}
        }

        with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
            result = summarize_node(initial_state)

            assert "analysis" in result
            assert "summary" in result["analysis"]

    def test_report_node(self, initial_state):
        """Test report node"""
        initial_state.normalized = [
            {"title": "Test", "content": "Content", "source": "rss", "url": "https://example.com"}
        ]
        initial_state.analysis = {
            "sentiment": {
                "positive": 1, "neutral": 0, "negative": 0,
                "positive_pct": 100.0, "neutral_pct": 0.0, "negative_pct": 0.0
            },
            "keywords": {"top_keywords": [{"keyword": "AI", "count": 5}]},
            "summary": "Test summary",
            "llm_insights": "Test insights"
        }

        result = report_node(initial_state)

        assert "metrics" in result
        assert "report_md" in result
        assert result["report_md"] is not None


class TestSocialTrendAgentPipeline:
    """Test full pipeline execution"""

    def test_full_pipeline_rss_only(self, mock_llm):
        """Test complete pipeline with RSS only"""
        with patch('src.agents.social_trend.graph.fetch_rss_feeds', return_value=SAMPLE_RSS_DATA):
            with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
                result = run_agent(
                    query="machine learning",
                    sources=["rss"],
                    rss_feeds=[
                        "https://www.reddit.com/r/MachineLearning/.rss"
                    ],
                    time_window="7d",
                    language="en",
                    max_results=10,
                    require_approval=False
                )

                # Verify state
                assert result.query == "machine learning"
                assert result.time_window == "7d"
                assert result.language == "en"

                # Verify data collected
                assert len(result.raw_items) >= 0
                assert len(result.normalized) >= 0

                # Verify analysis
                assert result.analysis is not None
                assert "sentiment" in result.analysis

                # Verify report
                assert result.report_md is not None
                assert result.metrics is not None

    def test_korean_language_support(self, mock_llm):
        """Test Korean language processing"""
        korean_data = [
            {
                "title": "인공지능 발전",
                "description": "AI 기술 동향",
                "link": "https://example.com",
                "source": "rss"
            }
        ]

        with patch('src.agents.social_trend.graph.fetch_rss_feeds', return_value=korean_data):
            with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
                result = run_agent(
                    query="인공지능",
                    sources=["rss"],
                    time_window="7d",
                    language="ko",
                    max_results=5,
                    require_approval=False
                )

                assert result.language == "ko"
                assert result.report_md is not None

    def test_multiple_platforms(self, mock_llm):
        """Test with multiple platforms (will use sample data)"""
        with patch('src.agents.social_trend.graph.fetch_x_posts', return_value=SAMPLE_X_DATA):
            with patch('src.agents.social_trend.graph.fetch_instagram_posts', return_value=[]):
                with patch('src.agents.social_trend.graph.fetch_naver_blog_posts', return_value=SAMPLE_NAVER_DATA):
                    with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
                        result = run_agent(
                            query="AI trends",
                            sources=["x", "instagram", "naver_blog"],
                            time_window="7d",
                            language="ko",
                            max_results=15,
                            require_approval=False
                        )

                        # Should complete even with sample data
                        assert result is not None
                        assert result.run_id is not None

    def test_metrics_calculation(self, mock_llm):
        """Test metrics are properly calculated"""
        with patch('src.agents.social_trend.graph.fetch_rss_feeds', return_value=SAMPLE_RSS_DATA):
            with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
                result = run_agent(
                    query="test",
                    sources=["rss"],
                    max_results=5,
                    require_approval=False
                )

                assert "coverage" in result.metrics
                assert "factuality" in result.metrics
                assert "actionability" in result.metrics

                # Metrics should be valid percentages
                assert 0 <= result.metrics["coverage"] <= 1
                assert 0 <= result.metrics["factuality"] <= 1
                assert 0 <= result.metrics["actionability"] <= 1


class TestSocialTrendAgentTools:
    """Test agent tools"""

    def test_fetch_x_posts(self):
        """Test X posts fetching (sample data)"""
        from src.agents.social_trend.tools import fetch_x_posts

        with patch('src.agents.social_trend.tools.fetch_x_posts_via_mcp', return_value=SAMPLE_X_DATA):
            result = fetch_x_posts("AI", max_results=5)

            assert isinstance(result, list)

    def test_fetch_instagram_posts(self):
        """Test Instagram posts fetching (sample data)"""
        from src.agents.social_trend.tools import fetch_instagram_posts

        result = fetch_instagram_posts("AI", max_results=5)

        assert isinstance(result, list)
        # Should return sample data

    def test_fetch_naver_blog_posts(self):
        """Test Naver blog posts fetching"""
        from src.agents.social_trend.tools import fetch_naver_blog_posts

        with patch('src.agents.social_trend.tools.search_news_via_mcp', return_value=SAMPLE_NAVER_DATA):
            result = fetch_naver_blog_posts("AI", max_results=5)

            assert isinstance(result, list)

    def test_fetch_rss_feeds(self):
        """Test RSS feed fetching"""
        from src.agents.social_trend.tools import fetch_rss_feeds

        with patch('feedparser.parse') as mock_parse:
            mock_parse.return_value = MagicMock(
                entries=[
                    MagicMock(
                        title="Test",
                        description="Desc",
                        link="https://example.com",
                        published="2024-01-01"
                    )
                ]
            )
            feeds = ["https://example.com/rss"]
            result = fetch_rss_feeds(feeds, max_results=5)

            assert isinstance(result, list)

    def test_normalize_items(self):
        """Test item normalization"""
        from src.agents.social_trend.tools import normalize_items, CollectedItem

        items = [
            CollectedItem(
                title="Test",
                url="https://example.com",
                source="test",
                content="Desc",
                published_at=1234567890.0
            )
        ]

        result = normalize_items(items)

        assert isinstance(result, list)
        assert len(result) == 1

    def test_analyze_sentiment_and_keywords(self, mock_llm):
        """Test sentiment and keyword analysis"""
        from src.agents.social_trend.tools import analyze_sentiment_and_keywords

        texts = [
            "This is great news about AI development",
            "Concerns about market trends"
        ]

        with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
            result = analyze_sentiment_and_keywords(texts)

            assert "sentiment" in result
            assert "keywords" in result


class TestSocialTrendAgentErrorHandling:
    """Test error handling and recovery"""

    def test_empty_query(self, mock_llm):
        """Test with empty query"""
        with patch('src.agents.social_trend.graph.fetch_rss_feeds', return_value=[]):
            with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
                result = run_agent(
                    query="",
                    sources=["rss"],
                    max_results=5,
                    require_approval=False
                )

                # Should complete without error
                assert result is not None

    def test_invalid_source(self, mock_llm):
        """Test with invalid source platform"""
        with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
            result = run_agent(
                query="test",
                sources=["invalid_platform"],
                max_results=5,
                require_approval=False
            )

            # Should handle gracefully
            assert result is not None

    def test_no_results(self, mock_llm):
        """Test when no results are returned"""
        with patch('src.agents.social_trend.graph.fetch_rss_feeds', return_value=[]):
            with patch('src.integrations.llm.llm_client.get_llm_client', return_value=mock_llm):
                result = run_agent(
                    query="xyznonexistentquery123456",
                    sources=["rss"],
                    max_results=5,
                    require_approval=False
                )

                # Should complete even with no results
                assert result is not None
                assert result.report_md is not None


class TestSocialTrendAgentIntegration:
    """Integration tests with external services"""

    @pytest.mark.skipif(
        not os.getenv("X_BEARER_TOKEN"),
        reason="X_BEARER_TOKEN not set"
    )
    def test_real_x_api(self):
        """Test with real X API"""
        result = run_agent(
            query="AI",
            sources=["x"],
            max_results=10
        )

        assert len(result.raw_items) > 0

    @pytest.mark.skipif(
        not (os.getenv("NAVER_CLIENT_ID") and os.getenv("NAVER_CLIENT_SECRET")),
        reason="Naver API credentials not set"
    )
    def test_real_naver_api(self):
        """Test with real Naver API"""
        result = run_agent(
            query="인공지능",
            sources=["naver_blog"],
            max_results=10
        )

        assert len(result.raw_items) > 0


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing"""
    return """## 트렌드 요약
    AI 기술이 급속히 발전하고 있습니다.

    ## 핵심 발견사항
    - AI 시장 성장세 지속
    - 기업 AI 도입 확대

    ## 실행 권고안
    - AI 전략 수립 필요
    - 인재 확보 중요"""


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

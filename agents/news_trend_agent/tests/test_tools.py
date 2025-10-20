"""
Unit tests for news_trend_agent tools
"""
import pytest
from agents.news_trend_agent.tools import (
    search_news,
    analyze_sentiment,
    extract_keywords,
    summarize_trend,
    _parse_time_window,
    _get_sample_news
)


class TestSearchNews:
    """Tests for search_news function"""

    def test_search_news_with_sample_data(self):
        """Test news search falls back to sample data"""
        results = search_news(
            query="전기차",
            time_window="7d",
            language="ko",
            max_results=5
        )

        assert isinstance(results, list)
        assert len(results) <= 5
        assert all("title" in item for item in results)
        assert all("url" in item for item in results)

    def test_search_news_english(self):
        """Test English news search"""
        results = search_news(
            query="electric vehicle",
            time_window="24h",
            language="en",
            max_results=10
        )

        assert isinstance(results, list)
        assert len(results) <= 10

    def test_parse_time_window_hours(self):
        """Test parsing time window in hours"""
        from datetime import datetime, timedelta

        result = _parse_time_window("24h")
        expected = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d")

        assert result == expected

    def test_parse_time_window_days(self):
        """Test parsing time window in days"""
        from datetime import datetime, timedelta

        result = _parse_time_window("7d")
        expected = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        assert result == expected

    def test_get_sample_news_korean(self):
        """Test sample news generation for Korean"""
        samples = _get_sample_news("전기차", "7d", "ko")

        assert isinstance(samples, list)
        assert len(samples) > 0
        assert all("title" in item for item in samples)
        assert all("전기차" in item["title"] or "전기차" in item["description"] for item in samples)

    def test_get_sample_news_english(self):
        """Test sample news generation for English"""
        samples = _get_sample_news("electric vehicle", "7d", "en")

        assert isinstance(samples, list)
        assert all("electric vehicle" in item["title"].lower() or
                  "electric vehicle" in item["description"].lower()
                  for item in samples)


class TestAnalyzeSentiment:
    """Tests for analyze_sentiment function"""

    def test_positive_sentiment(self):
        """Test positive sentiment detection"""
        items = [
            {"title": "성공적인 성장", "description": "긍정적인 호평"},
            {"title": "증가하는 트렌드", "description": "좋은 반응"}
        ]

        result = analyze_sentiment(items)

        assert result["positive"] > 0
        assert result["positive_pct"] > 0

    def test_negative_sentiment(self):
        """Test negative sentiment detection"""
        items = [
            {"title": "실패한 프로젝트", "description": "부정적 비판"},
            {"title": "하락하는 추세", "description": "감소"}
        ]

        result = analyze_sentiment(items)

        assert result["negative"] > 0
        assert result["negative_pct"] > 0

    def test_neutral_sentiment(self):
        """Test neutral sentiment detection"""
        items = [
            {"title": "중립적 제목", "description": "사실 전달"}
        ]

        result = analyze_sentiment(items)

        assert result["neutral"] > 0

    def test_sentiment_percentages_sum_to_100(self):
        """Test that sentiment percentages sum to 100"""
        items = [
            {"title": "성공", "description": "긍정"},
            {"title": "실패", "description": "부정"},
            {"title": "중립", "description": "보통"}
        ]

        result = analyze_sentiment(items)

        total_pct = (
            result["positive_pct"] +
            result["neutral_pct"] +
            result["negative_pct"]
        )

        assert abs(total_pct - 100.0) < 0.1  # Allow small floating point error

    def test_empty_items(self):
        """Test sentiment analysis with empty items"""
        result = analyze_sentiment([])

        assert result["positive"] == 0
        assert result["neutral"] == 0
        assert result["negative"] == 0


class TestExtractKeywords:
    """Tests for extract_keywords function"""

    def test_keyword_extraction(self):
        """Test basic keyword extraction"""
        items = [
            {"title": "전기차 배터리 충전", "description": "전기차 관련 뉴스"},
            {"title": "배터리 기술 발전", "description": "충전 인프라 확대"}
        ]

        result = extract_keywords(items)

        assert "top_keywords" in result
        assert "total_unique_keywords" in result
        assert len(result["top_keywords"]) > 0

        # Check that common words appear
        keywords = [kw["keyword"] for kw in result["top_keywords"]]
        assert "전기차" in keywords or "배터리" in keywords

    def test_keyword_counts(self):
        """Test keyword frequency counting"""
        items = [
            {"title": "전기차 전기차 전기차", "description": "전기차"}
        ]

        result = extract_keywords(items)
        top_keyword = result["top_keywords"][0]

        assert top_keyword["keyword"] == "전기차"
        assert top_keyword["count"] == 4  # Appears 4 times

    def test_stopword_filtering(self):
        """Test that stop words are filtered out"""
        items = [
            {"title": "이 것은 그 무엇", "description": "을 를 이 가"}
        ]

        result = extract_keywords(items)
        keywords = [kw["keyword"] for kw in result["top_keywords"]]

        # Stop words should be filtered
        assert "이" not in keywords
        assert "를" not in keywords

    def test_empty_items(self):
        """Test keyword extraction with empty items"""
        result = extract_keywords([])

        assert result["top_keywords"] == []
        assert result["total_unique_keywords"] == 0


class TestSummarizeTrend:
    """Tests for summarize_trend function"""

    def test_positive_trend_summary(self):
        """Test summary for positive trend"""
        items = [
            {"title": "긍정적", "description": "성공"}
        ]
        analysis = {
            "sentiment": {
                "positive_pct": 80,
                "neutral_pct": 15,
                "negative_pct": 5
            },
            "keywords": {
                "top_keywords": [
                    {"keyword": "전기차", "count": 10},
                    {"keyword": "배터리", "count": 5}
                ]
            }
        }

        summary = summarize_trend("전기차", items, analysis)

        assert "긍정적" in summary
        assert "전기차" in summary

    def test_negative_trend_summary(self):
        """Test summary for negative trend"""
        items = []
        analysis = {
            "sentiment": {
                "positive_pct": 10,
                "neutral_pct": 20,
                "negative_pct": 70
            },
            "keywords": {
                "top_keywords": []
            }
        }

        summary = summarize_trend("실패 사례", items, analysis)

        assert "부정적" in summary

    def test_action_recommendations_included(self):
        """Test that action recommendations are included"""
        items = []
        analysis = {
            "sentiment": {
                "positive_pct": 50,
                "neutral_pct": 30,
                "negative_pct": 20
            },
            "keywords": {
                "top_keywords": [
                    {"keyword": "키워드", "count": 5}
                ]
            }
        }

        summary = summarize_trend("테스트", items, analysis)

        assert "실행 권고안" in summary
        assert "마케팅" in summary or "SEO" in summary


# Pytest fixtures
@pytest.fixture
def sample_news_items():
    """Fixture providing sample news items"""
    return [
        {
            "title": "전기차 시장 성장",
            "description": "전기차 판매가 증가하고 있습니다",
            "url": "https://example.com/news1",
            "source": {"name": "Sample News"},
            "publishedAt": "2024-10-19T10:00:00Z",
            "content": "전기차 시장 분석"
        },
        {
            "title": "배터리 기술 혁신",
            "description": "새로운 배터리 기술이 개발되었습니다",
            "url": "https://example.com/news2",
            "source": {"name": "Sample News"},
            "publishedAt": "2024-10-18T15:00:00Z",
            "content": "배터리 혁신 내용"
        }
    ]


def test_full_pipeline(sample_news_items):
    """Test full analysis pipeline"""
    # 1. Sentiment analysis
    sentiment = analyze_sentiment(sample_news_items)
    assert sentiment is not None

    # 2. Keyword extraction
    keywords = extract_keywords(sample_news_items)
    assert len(keywords["top_keywords"]) > 0

    # 3. Trend summary
    analysis = {
        "sentiment": sentiment,
        "keywords": keywords
    }
    summary = summarize_trend("전기차", sample_news_items, analysis)
    assert len(summary) > 0

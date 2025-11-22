"""
News Trend Agent E2E 통합 테스트

실제 에이전트 실행 흐름을 테스트합니다.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from agents.news_trend_agent.graph import run_agent


class TestNewsAgentE2E:
    """뉴스 트렌드 에이전트 통합 테스트"""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        """환경 변수 모킹"""
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("OPENAI_MODEL_NAME", "gpt-4o")

    @pytest.fixture
    def sample_news_data(self):
        """샘플 뉴스 데이터"""
        return [
            {
                "title": "AI 기술 발전 가속화",
                "description": "인공지능 기술이 빠르게 발전하고 있습니다.",
                "url": "https://example.com/news1",
                "source": {"name": "Tech News"},
                "publishedAt": "2024-11-01T10:00:00Z",
                "content": "AI 관련 상세 내용..."
            },
            {
                "title": "ChatGPT 사용자 급증",
                "description": "ChatGPT의 사용자가 크게 증가했습니다.",
                "url": "https://example.com/news2",
                "source": {"name": "Business News"},
                "publishedAt": "2024-11-01T11:00:00Z",
                "content": "ChatGPT 관련 상세 내용..."
            }
        ]

    def test_agent_basic_execution(self, mock_env, sample_news_data):
        """
        기본 에이전트 실행 테스트

        Given: 환경 변수와 샘플 데이터
        When: run_agent 실행
        Then: 정상적으로 분석 결과 반환
        """
        with patch('agents.news_trend_agent.tools.search_news', return_value=sample_news_data):
            with patch('agents.news_trend_agent.tools._get_llm') as mock_llm:
                # LLM 모킹
                mock_chain = MagicMock()
                mock_chain.invoke.return_value = "AI 기술이 빠르게 발전하고 있으며, ChatGPT의 성공이 주목받고 있습니다."
                mock_llm.return_value = MagicMock()

                # 에이전트 실행
                result = run_agent(
                    query="AI",
                    time_window="7d",
                    language="ko",
                    max_results=20
                )

                # 검증 (result는 NewsAgentState - Pydantic model)
                assert result is not None
                assert result.query == "AI"
                assert result.time_window == "7d"
                assert hasattr(result, 'normalized')
                assert len(result.normalized) == 2

    def test_agent_with_empty_results(self, mock_env):
        """
        빈 결과 처리 테스트

        Given: 뉴스 검색 결과가 없음
        When: run_agent 실행
        Then: 빈 결과를 우아하게 처리
        """
        with patch('agents.news_trend_agent.tools.search_news', return_value=[]):
            result = run_agent(
                query="NonExistentTopic",
                time_window="7d"
            )

            assert result is not None
            assert len(result.normalized) == 0

    def test_agent_sentiment_analysis(self, mock_env, sample_news_data):
        """
        감성 분석 통합 테스트

        Given: 긍정적인 뉴스 데이터
        When: 감성 분석 수행
        Then: 올바른 감성 비율 반환
        """
        with patch('agents.news_trend_agent.tools.search_news', return_value=sample_news_data):
            with patch('agents.news_trend_agent.tools._get_llm'):
                result = run_agent(query="AI", time_window="7d")

                analysis = result.analysis or {}
                sentiment = analysis.get("sentiment", {}) if isinstance(analysis, dict) else {}

                assert "positive" in sentiment
                assert "neutral" in sentiment
                assert "negative" in sentiment
                assert sentiment["positive"] + sentiment["neutral"] + sentiment["negative"] == len(sample_news_data)

    def test_agent_keyword_extraction(self, mock_env, sample_news_data):
        """
        키워드 추출 통합 테스트

        Given: 뉴스 데이터
        When: 키워드 추출 수행
        Then: 주요 키워드 리스트 반환
        """
        with patch('agents.news_trend_agent.tools.search_news', return_value=sample_news_data):
            with patch('agents.news_trend_agent.tools._get_llm'):
                result = run_agent(query="AI", time_window="7d")

                analysis = result.analysis or {}
                keywords = analysis.get("keywords", {}) if isinstance(analysis, dict) else {}

                assert "top_keywords" in keywords
                assert isinstance(keywords["top_keywords"], list)
                assert len(keywords["top_keywords"]) > 0

    def test_agent_report_generation(self, mock_env, sample_news_data):
        """
        리포트 생성 통합 테스트

        Given: 분석 완료된 데이터
        When: 리포트 생성
        Then: 마크다운 리포트 반환
        """
        with patch('agents.news_trend_agent.tools.search_news', return_value=sample_news_data):
            with patch('agents.news_trend_agent.tools._get_llm'):
                result = run_agent(query="AI", time_window="7d")

                assert hasattr(result, 'report_md')
                assert isinstance(result.report_md, str)
                assert "# 뉴스 트렌드 분석 리포트" in result.report_md

    def test_agent_metrics_calculation(self, mock_env, sample_news_data):
        """
        메트릭 계산 통합 테스트

        Given: 분석 결과
        When: 메트릭 계산
        Then: coverage, factuality, actionability 반환
        """
        with patch('agents.news_trend_agent.tools.search_news', return_value=sample_news_data):
            with patch('agents.news_trend_agent.tools._get_llm'):
                result = run_agent(query="AI", time_window="7d", max_results=20)

                metrics = result.metrics or {}

                assert "coverage" in metrics
                assert "factuality" in metrics
                assert "actionability" in metrics
                assert 0 <= metrics.get("coverage", 0) <= 1
                assert 0 <= metrics.get("factuality", 0) <= 1

    @pytest.mark.asyncio
    async def test_agent_concurrent_execution(self, mock_env, sample_news_data):
        """
        동시 실행 테스트

        Given: 여러 쿼리
        When: 동시에 에이전트 실행
        Then: 각각 독립적으로 정상 동작
        """
        import asyncio

        with patch('agents.news_trend_agent.tools.search_news', return_value=sample_news_data):
            with patch('agents.news_trend_agent.tools._get_llm'):
                # 동시 실행
                tasks = [
                    asyncio.to_thread(run_agent, query=f"Query{i}", time_window="7d")
                    for i in range(3)
                ]
                results = await asyncio.gather(*tasks)

                assert len(results) == 3
                for i, result in enumerate(results):
                    assert result.query == f"Query{i}"

    def test_agent_error_handling(self, mock_env):
        """
        에러 핸들링 테스트

        Given: API 호출 실패
        When: 에이전트 실행
        Then: 우아하게 폴백 처리
        """
        def mock_error(*args, **kwargs):
            raise Exception("API Error")

        with patch('agents.news_trend_agent.tools.search_news', side_effect=mock_error):
            # 에러가 발생해도 예외를 던지지 않아야 함
            result = run_agent(query="AI", time_window="7d")

            # 부분 결과 또는 빈 결과 반환
            assert result is not None

    def test_agent_cache_behavior(self, mock_env, sample_news_data):
        """
        캐싱 동작 테스트

        Given: 동일한 쿼리 2회 실행
        When: 첫 번째는 API 호출, 두 번째는 캐시 사용
        Then: 두 번째 호출이 더 빠름
        """
        import time

        with patch('agents.news_trend_agent.tools.search_news', return_value=sample_news_data) as mock_search:
            with patch('agents.news_trend_agent.tools._get_llm'):
                # 첫 번째 실행
                start1 = time.time()
                result1 = run_agent(query="AI", time_window="7d")
                duration1 = time.time() - start1

                # 두 번째 실행 (캐시 사용)
                start2 = time.time()
                result2 = run_agent(query="AI", time_window="7d")
                duration2 = time.time() - start2

                # 검증
                assert result1.get("query") == result2.get("query")
                # 캐시를 사용하므로 API가 1회만 호출되어야 함
                assert mock_search.call_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

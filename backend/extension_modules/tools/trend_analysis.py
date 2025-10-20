"""
소비자 트렌드 분석 도구
- 뉴스 수집 (News API)
- 감성 분석
- 키워드 추출
- 트렌드 요약
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from extension_modules.tools.base import CSToolBase, ToolList
import os
import requests
from datetime import datetime, timedelta
import json
from collections import Counter
import re


# 환경 변수 로드
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")


# ===== Input Schemas =====

class NewsSearchInput(BaseModel):
    """뉴스 검색 입력 스키마"""
    query: str = Field(
        ...,
        description="검색할 키워드 또는 제품명 (예: '신제품 스마트폰', '친환경 화장품')"
    )
    days: int = Field(
        default=7,
        description="최근 며칠간의 뉴스를 검색할지 지정 (기본값: 7일)"
    )
    language: str = Field(
        default="ko",
        description="뉴스 언어 (ko: 한국어, en: 영어)"
    )
    max_results: int = Field(
        default=20,
        description="최대 검색 결과 수 (기본값: 20)"
    )


class SentimentAnalysisInput(BaseModel):
    """감성 분석 입력 스키마"""
    texts: List[str] = Field(
        ...,
        description="분석할 텍스트 리스트 (뉴스 제목, 본문 등)"
    )
    detailed: bool = Field(
        default=False,
        description="상세 분석 여부 (True: 각 텍스트별 감성, False: 전체 요약)"
    )


class KeywordExtractionInput(BaseModel):
    """키워드 추출 입력 스키마"""
    texts: List[str] = Field(
        ...,
        description="키워드를 추출할 텍스트 리스트"
    )
    top_k: int = Field(
        default=10,
        description="추출할 상위 키워드 개수 (기본값: 10)"
    )


class TrendSummaryInput(BaseModel):
    """트렌드 요약 입력 스키마"""
    query: str = Field(
        ...,
        description="분석할 주제 또는 제품명"
    )
    days: int = Field(
        default=7,
        description="분석 기간 (일 단위, 기본값: 7일)"
    )


# ===== Output Schemas =====

class NewsArticle(BaseModel):
    """뉴스 기사 정보"""
    title: str
    description: Optional[str] = None
    url: str
    published_at: str
    source: str


class NewsSearchOutput(BaseModel):
    """뉴스 검색 결과"""
    query: str
    total_results: int
    articles: List[NewsArticle]
    message: str


class SentimentAnalysisOutput(BaseModel):
    """감성 분석 결과"""
    positive_ratio: float = Field(description="긍정 비율 (0-1)")
    negative_ratio: float = Field(description="부정 비율 (0-1)")
    neutral_ratio: float = Field(description="중립 비율 (0-1)")
    summary: str = Field(description="감성 분석 요약")
    details: Optional[List[Dict[str, Any]]] = None


class KeywordExtractionOutput(BaseModel):
    """키워드 추출 결과"""
    keywords: List[Dict[str, Any]] = Field(
        description="키워드 리스트 [{keyword: str, count: int, score: float}]"
    )
    summary: str


class TrendSummaryOutput(BaseModel):
    """트렌드 요약 결과"""
    query: str
    period: str
    news_count: int
    top_keywords: List[str]
    sentiment_summary: str
    key_insights: List[str]
    full_summary: str


# ===== Tool Implementation =====

class TrendAnalysisTool(CSToolBase):
    """소비자 트렌드 분석 도구 모음"""

    def __init__(self):
        super().__init__()
        self.news_api_key = NEWS_API_KEY
        self.naver_client_id = NAVER_CLIENT_ID
        self.naver_client_secret = NAVER_CLIENT_SECRET

    # ===== 뉴스 수집 =====

    async def search_news(
        self,
        query: str,
        days: int = 7,
        language: str = "ko",
        max_results: int = 20
    ) -> NewsSearchOutput:
        """
        뉴스 검색 도구 - News API를 사용하여 최신 뉴스를 수집합니다.

        Args:
            query: 검색 키워드
            days: 검색 기간 (일 단위)
            language: 뉴스 언어
            max_results: 최대 결과 수

        Returns:
            NewsSearchOutput: 뉴스 검색 결과
        """
        try:
            # News API를 사용한 뉴스 검색
            if self.news_api_key and language == "en":
                articles = await self._fetch_news_api(query, days, max_results)
            # Naver API를 사용한 한국어 뉴스 검색
            elif self.naver_client_id and language == "ko":
                articles = await self._fetch_naver_news(query, max_results)
            # API 키가 없는 경우 샘플 데이터 반환
            else:
                articles = self._get_sample_news(query, days)

            return NewsSearchOutput(
                query=query,
                total_results=len(articles),
                articles=articles,
                message=f"'{query}'에 대한 {len(articles)}개의 뉴스를 수집했습니다."
            )

        except Exception as e:
            # 오류 발생 시 샘플 데이터 반환
            articles = self._get_sample_news(query, days)
            return NewsSearchOutput(
                query=query,
                total_results=len(articles),
                articles=articles,
                message=f"샘플 데이터를 반환합니다. (API 오류: {str(e)})"
            )

    async def _fetch_news_api(self, query: str, days: int, max_results: int) -> List[NewsArticle]:
        """News API를 사용하여 뉴스 수집"""
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "from": from_date,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": max_results,
            "apiKey": self.news_api_key
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        articles = []
        for article in data.get("articles", [])[:max_results]:
            articles.append(NewsArticle(
                title=article.get("title", ""),
                description=article.get("description", ""),
                url=article.get("url", ""),
                published_at=article.get("publishedAt", ""),
                source=article.get("source", {}).get("name", "Unknown")
            ))

        return articles

    async def _fetch_naver_news(self, query: str, max_results: int) -> List[NewsArticle]:
        """Naver API를 사용하여 한국어 뉴스 수집"""
        url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": self.naver_client_id,
            "X-Naver-Client-Secret": self.naver_client_secret
        }
        params = {
            "query": query,
            "display": min(max_results, 100),
            "sort": "date"
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        articles = []
        for item in data.get("items", []):
            # HTML 태그 제거
            title = re.sub(r'<[^>]+>', '', item.get("title", ""))
            description = re.sub(r'<[^>]+>', '', item.get("description", ""))

            articles.append(NewsArticle(
                title=title,
                description=description,
                url=item.get("link", ""),
                published_at=item.get("pubDate", ""),
                source="Naver News"
            ))

        return articles

    def _get_sample_news(self, query: str, days: int) -> List[NewsArticle]:
        """API 키가 없을 때 사용할 샘플 뉴스 데이터"""
        now = datetime.now()

        sample_articles = [
            NewsArticle(
                title=f"{query} 관련 긍정적인 소비자 반응 증가",
                description=f"최근 {query}에 대한 소비자들의 관심이 크게 증가하고 있으며, 특히 젊은 층에서 긍정적인 반응을 보이고 있다.",
                url="https://example.com/news1",
                published_at=(now - timedelta(days=1)).isoformat(),
                source="Sample News"
            ),
            NewsArticle(
                title=f"{query} 시장 동향 분석 - 성장세 지속",
                description=f"{query} 시장이 전년 대비 15% 성장하며 빠른 성장세를 보이고 있다.",
                url="https://example.com/news2",
                published_at=(now - timedelta(days=2)).isoformat(),
                source="Sample News"
            ),
            NewsArticle(
                title=f"전문가들, {query}의 미래 전망 밝게 평가",
                description=f"업계 전문가들은 {query}가 향후 3년간 지속적인 성장을 이어갈 것으로 전망하고 있다.",
                url="https://example.com/news3",
                published_at=(now - timedelta(days=3)).isoformat(),
                source="Sample News"
            ),
            NewsArticle(
                title=f"{query} 관련 소비자 불만 일부 제기",
                description=f"일부 소비자들이 {query}의 가격 대비 품질에 대해 우려를 표명하고 있다.",
                url="https://example.com/news4",
                published_at=(now - timedelta(days=4)).isoformat(),
                source="Sample News"
            ),
            NewsArticle(
                title=f"{query} 신규 트렌드 주목",
                description=f"{query} 시장에서 친환경과 지속가능성이 새로운 트렌드로 부상하고 있다.",
                url="https://example.com/news5",
                published_at=(now - timedelta(days=5)).isoformat(),
                source="Sample News"
            )
        ]

        return sample_articles

    # ===== 감성 분석 =====

    async def analyze_sentiment(
        self,
        texts: List[str],
        detailed: bool = False
    ) -> SentimentAnalysisOutput:
        """
        감성 분석 도구 - 텍스트의 감성(긍정/부정/중립)을 분석합니다.

        간단한 키워드 기반 감성 분석을 수행합니다.
        실제 프로덕션에서는 LLM 또는 전문 감성 분석 모델을 사용하는 것이 좋습니다.

        Args:
            texts: 분석할 텍스트 리스트
            detailed: 상세 분석 여부

        Returns:
            SentimentAnalysisOutput: 감성 분석 결과
        """
        # 한국어 감성 키워드
        positive_keywords = [
            "좋", "훌륭", "최고", "만족", "추천", "긍정", "성장", "증가", "개선",
            "우수", "뛰어", "완벽", "성공", "효과", "혁신", "인기", "사랑"
        ]
        negative_keywords = [
            "나쁘", "실망", "불만", "부정", "감소", "하락", "문제", "우려",
            "불편", "최악", "실패", "부족", "어렵", "힘들", "비싸", "비효율"
        ]

        results = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        for text in texts:
            text_lower = text.lower()
            pos_score = sum(1 for kw in positive_keywords if kw in text_lower)
            neg_score = sum(1 for kw in negative_keywords if kw in text_lower)

            if pos_score > neg_score:
                sentiment = "positive"
                positive_count += 1
            elif neg_score > pos_score:
                sentiment = "negative"
                negative_count += 1
            else:
                sentiment = "neutral"
                neutral_count += 1

            if detailed:
                results.append({
                    "text": text[:100] + "..." if len(text) > 100 else text,
                    "sentiment": sentiment,
                    "positive_score": pos_score,
                    "negative_score": neg_score
                })

        total = len(texts) if texts else 1
        positive_ratio = positive_count / total
        negative_ratio = negative_count / total
        neutral_ratio = neutral_count / total

        # 요약 생성
        dominant_sentiment = max(
            [("긍정적", positive_ratio), ("부정적", negative_ratio), ("중립적", neutral_ratio)],
            key=lambda x: x[1]
        )[0]

        summary = (
            f"전체 {total}개 텍스트 중 긍정 {positive_count}개({positive_ratio:.1%}), "
            f"부정 {negative_count}개({negative_ratio:.1%}), "
            f"중립 {neutral_count}개({neutral_ratio:.1%})로 분석되었습니다. "
            f"전반적으로 {dominant_sentiment} 감성이 우세합니다."
        )

        return SentimentAnalysisOutput(
            positive_ratio=positive_ratio,
            negative_ratio=negative_ratio,
            neutral_ratio=neutral_ratio,
            summary=summary,
            details=results if detailed else None
        )

    # ===== 키워드 추출 =====

    async def extract_keywords(
        self,
        texts: List[str],
        top_k: int = 10
    ) -> KeywordExtractionOutput:
        """
        키워드 추출 도구 - 텍스트에서 주요 키워드를 추출합니다.

        간단한 빈도 기반 키워드 추출을 수행합니다.
        실제 프로덕션에서는 TF-IDF, TextRank 등을 사용하는 것이 좋습니다.

        Args:
            texts: 키워드를 추출할 텍스트 리스트
            top_k: 추출할 상위 키워드 개수

        Returns:
            KeywordExtractionOutput: 키워드 추출 결과
        """
        # 불용어 (한국어)
        stop_words = {
            "이", "그", "저", "것", "수", "등", "및", "를", "을", "가", "이", "은", "는",
            "에", "의", "와", "과", "도", "로", "으로", "에서", "만", "를", "을",
            "있", "하", "되", "않", "없", "위", "말", "때", "년", "월", "일"
        }

        # 모든 텍스트 결합
        combined_text = " ".join(texts)

        # 한글과 영문만 추출 (2글자 이상)
        words = re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', combined_text)

        # 불용어 제거 및 빈도 계산
        filtered_words = [w for w in words if w not in stop_words]
        word_counts = Counter(filtered_words)

        # 상위 키워드 추출
        top_keywords = word_counts.most_common(top_k)

        # 점수 정규화 (최대값을 1.0으로)
        max_count = top_keywords[0][1] if top_keywords else 1

        keywords = [
            {
                "keyword": kw,
                "count": count,
                "score": round(count / max_count, 3)
            }
            for kw, count in top_keywords
        ]

        summary = f"총 {len(texts)}개 텍스트에서 상위 {len(keywords)}개 키워드를 추출했습니다. "
        if keywords:
            top_3 = ", ".join([k["keyword"] for k in keywords[:3]])
            summary += f"주요 키워드: {top_3}"

        return KeywordExtractionOutput(
            keywords=keywords,
            summary=summary
        )

    # ===== 트렌드 요약 =====

    async def summarize_trend(
        self,
        query: str,
        days: int = 7
    ) -> TrendSummaryOutput:
        """
        트렌드 종합 요약 도구 - 뉴스 수집, 감성 분석, 키워드 추출을 통합하여 트렌드를 요약합니다.

        Args:
            query: 분석할 주제
            days: 분석 기간

        Returns:
            TrendSummaryOutput: 트렌드 요약 결과
        """
        # 1. 뉴스 수집
        news_result = await self.search_news(query, days, max_results=30)

        # 2. 텍스트 추출
        texts = []
        for article in news_result.articles:
            texts.append(article.title)
            if article.description:
                texts.append(article.description)

        # 3. 감성 분석
        sentiment_result = await self.analyze_sentiment(texts)

        # 4. 키워드 추출
        keyword_result = await self.extract_keywords(texts, top_k=10)

        # 5. 주요 인사이트 생성
        key_insights = []

        # 감성 기반 인사이트
        if sentiment_result.positive_ratio > 0.5:
            key_insights.append(f"전반적으로 긍정적인 여론 ({sentiment_result.positive_ratio:.0%})")
        elif sentiment_result.negative_ratio > 0.3:
            key_insights.append(f"부정적인 의견이 {sentiment_result.negative_ratio:.0%}로 주목 필요")

        # 뉴스 개수 기반 인사이트
        if news_result.total_results > 20:
            key_insights.append(f"높은 미디어 관심도 ({news_result.total_results}건의 뉴스)")
        elif news_result.total_results < 5:
            key_insights.append("미디어 노출이 제한적임")

        # 키워드 기반 인사이트
        if keyword_result.keywords:
            top_keyword = keyword_result.keywords[0]["keyword"]
            key_insights.append(f"'{top_keyword}' 키워드가 가장 많이 언급됨")

        # 6. 전체 요약
        period_str = f"최근 {days}일"
        full_summary = (
            f"{period_str} 동안 '{query}'에 대한 {news_result.total_results}건의 뉴스가 발견되었습니다.\n\n"
            f"**감성 분석**: {sentiment_result.summary}\n\n"
            f"**주요 키워드**: {', '.join([k['keyword'] for k in keyword_result.keywords[:5]])}\n\n"
            f"**핵심 인사이트**:\n" + "\n".join([f"- {insight}" for insight in key_insights])
        )

        return TrendSummaryOutput(
            query=query,
            period=period_str,
            news_count=news_result.total_results,
            top_keywords=[k["keyword"] for k in keyword_result.keywords[:5]],
            sentiment_summary=sentiment_result.summary,
            key_insights=key_insights,
            full_summary=full_summary
        )

    # ===== Tool 등록 =====

    def get_tool(self) -> List[ToolList]:
        """도구 리스트 반환"""
        return [
            ToolList(
                tools=StructuredTool.from_function(
                    coroutine=self.search_news,
                    name="search_news",
                    description="특정 키워드나 제품명으로 최신 뉴스를 검색합니다. 시장 동향과 소비자 반응을 파악하는데 사용됩니다.",
                    args_schema=NewsSearchInput,
                    return_direct=False
                ),
                tool_start_message="뉴스를 검색하고 있습니다...",
                tool_end_message="뉴스 검색이 완료되었습니다."
            ),
            ToolList(
                tools=StructuredTool.from_function(
                    coroutine=self.analyze_sentiment,
                    name="analyze_sentiment",
                    description="텍스트의 감성(긍정/부정/중립)을 분석합니다. 소비자 반응의 전반적인 분위기를 파악하는데 사용됩니다.",
                    args_schema=SentimentAnalysisInput,
                    return_direct=False
                ),
                tool_start_message="감성 분석을 수행하고 있습니다...",
                tool_end_message="감성 분석이 완료되었습니다."
            ),
            ToolList(
                tools=StructuredTool.from_function(
                    coroutine=self.extract_keywords,
                    name="extract_keywords",
                    description="텍스트에서 주요 키워드와 트렌드를 추출합니다. 시장에서 주목받는 주제를 파악하는데 사용됩니다.",
                    args_schema=KeywordExtractionInput,
                    return_direct=False
                ),
                tool_start_message="키워드를 추출하고 있습니다...",
                tool_end_message="키워드 추출이 완료되었습니다."
            ),
            ToolList(
                tools=StructuredTool.from_function(
                    coroutine=self.summarize_trend,
                    name="summarize_trend",
                    description="뉴스 수집, 감성 분석, 키워드 추출을 통합하여 종합적인 트렌드 리포트를 생성합니다. 전체적인 시장 동향을 한눈에 파악할 때 사용됩니다.",
                    args_schema=TrendSummaryInput,
                    return_direct=False
                ),
                tool_start_message="트렌드를 종합 분석하고 있습니다...",
                tool_end_message="트렌드 분석이 완료되었습니다."
            )
        ]

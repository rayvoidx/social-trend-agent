from __future__ import annotations

import logging
import os
import re
import urllib3
from typing import Any, Dict, List, Optional

import requests  # type: ignore

try:
    from bs4 import BeautifulSoup  # type: ignore

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# SSL 경고 억제 (선택적)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class HttpMCP:
    """간단한 HTTP MCP: 지정된 URL을 가져와 텍스트/JSON 스니펫을 반환.

    - ENV/설정 불필요, 방화벽/화이트리스트 정책 하에서 사용 권장
    - 요청 수/타임아웃은 보수적으로 설정하여 LangGraph 노드 레이턴시에 영향 최소화
    - SSL 검증은 환경 변수 MCP_SSL_VERIFY로 제어 가능 (기본값: False)
    """

    def __init__(
        self, timeout: float = 5.0, max_bytes: int = 200_000, verify_ssl: Optional[bool] = None
    ):
        self.timeout = timeout
        self.max_bytes = max_bytes
        # SSL 검증 설정: 환경 변수 또는 파라미터로 제어
        if verify_ssl is None:
            verify_ssl = os.getenv("MCP_SSL_VERIFY", "false").lower() in ("true", "1", "yes")
        self.verify_ssl = verify_ssl

    def _extract_site_name(self, html_content: str, url: str) -> str:
        """HTML에서 사이트명 추출 (한국어 우선)"""
        if not BS4_AVAILABLE:
            return ""

        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # 1순위: og:site_name 메타 태그
            og_site_name = soup.find("meta", property="og:site_name")
            if og_site_name and og_site_name.get("content"):
                content = og_site_name.get("content")
                if isinstance(content, str):
                    site_name = content.strip()
                    if site_name:
                        return site_name

            # 2순위: title 태그
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                title = title_tag.string.strip()
                # 제목에서 불필요한 부분 제거 (예: " - 홈페이지", " | 사이트명")
                title = re.sub(r"\s*[-|]\s*.*$", "", title)
                if title:
                    return title

            # 3순위: h1 태그
            h1_tag = soup.find("h1")
            if h1_tag and h1_tag.string:
                h1_text = h1_tag.string.strip()
                if h1_text:
                    return h1_text

            # 4순위: meta description에서 추출 시도
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                content = meta_desc.get("content")
                if isinstance(content, str):
                    desc = content.strip()[:50]  # 처음 50자만
                    if desc:
                        return desc

            return ""
        except Exception as e:
            logger.debug(f"Failed to extract site name from {url}: {e}")
            return ""

    def _normalize_url(self, url: str) -> str:
        """URL 정규화 (공백 제거, 인코딩 등)"""
        if not url:
            return url
        # 공백 제거
        url = url.strip().replace(" ", "")
        # 여러 공백을 하나로
        import re

        url = re.sub(r"\s+", "", url)
        return url

    def fetch(self, url: str) -> Dict[str, Any]:
        """URL에서 콘텐츠 가져오기 (SSL 오류 시 자동 재시도)"""
        # URL 정규화
        url = self._normalize_url(url)

        # SSL 오류 발생 시 verify=False로 재시도
        ssl_errors = (
            requests.exceptions.SSLError,
            requests.exceptions.ConnectionError,
        )

        try:
            # 첫 시도: verify_ssl 설정 사용
            try:
                resp = requests.get(
                    url,
                    timeout=self.timeout,
                    headers={"User-Agent": "LangGraph-MCP/1.0"},
                    verify=self.verify_ssl,
                )
                resp.raise_for_status()
            except ssl_errors as ssl_err:
                # SSL 오류 발생 시 verify=False로 재시도
                logger.debug(f"SSL error for {url}, retrying with verify=False: {ssl_err}")
                if self.verify_ssl:  # verify_ssl이 True였던 경우에만 재시도
                    try:
                        resp = requests.get(
                            url,
                            timeout=self.timeout,
                            headers={"User-Agent": "LangGraph-MCP/1.0"},
                            verify=False,
                        )
                        resp.raise_for_status()
                    except Exception as retry_err:
                        logger.warning(
                            f"HTTP MCP fetch failed for {url} (retry failed): {retry_err}"
                        )
                        return {
                            "url": url,
                            "error": f"SSL error and retry failed: {str(retry_err)}",
                        }
                else:
                    # 이미 verify=False였으면 그냥 실패 처리
                    raise

            # 성공적으로 응답 받음
            ctype = resp.headers.get("content-type", "")
            content = resp.content[: self.max_bytes]
            text: str | None = None
            data: Any | None = None
            site_name: str = ""

            if "application/json" in ctype:
                try:
                    data = resp.json()
                except Exception:
                    text = content.decode("utf-8", errors="ignore")
            else:
                text = content.decode("utf-8", errors="ignore")
                # HTML인 경우 사이트명 추출 시도
                if text and ("text/html" in ctype or "html" in ctype.lower()):
                    site_name = self._extract_site_name(text, url)

            return {
                "url": url,
                "content_type": ctype,
                "text": text,
                "json": data,
                "status": resp.status_code,
                "site_name": site_name,  # 사이트명 추가
            }
        except Exception as e:
            # SSL 오류는 디버그 레벨, 기타 오류는 경고 레벨
            if isinstance(e, ssl_errors):
                logger.debug(f"HTTP MCP fetch failed for {url}: {e}")
            else:
                logger.warning(f"HTTP MCP fetch failed for {url}: {e}")
            return {"url": url, "error": str(e)}

    def fetch_many(self, urls: List[str], limit: int = 3) -> List[Dict[str, Any]]:
        """여러 URL에서 콘텐츠 가져오기 (실패한 URL은 건너뛰고 계속 진행)"""
        out: List[Dict[str, Any]] = []
        for u in urls[:limit]:
            # URL 정규화
            normalized_url = self._normalize_url(u)
            if not normalized_url:
                continue

            result = self.fetch(normalized_url)
            # 오류가 있더라도 결과에 포함 (나중에 필터링 가능)
            out.append(result)

            # 성공한 결과가 충분하면 조기 종료 (선택적)
            success_count = sum(1 for r in out if r.get("text") or r.get("json"))
            if success_count >= limit:
                break

        return out


# 간단한 웹 검색 MCP (Brave 또는 SerpAPI 중 사용 가능한 키로 호출)
class WebSearchMCP:
    """키워드로 최신 URL 후보를 가져오는 경량 MCP.

    - BRAVE_API_KEY 또는 SERPAPI_API_KEY 중 하나가 설정되어 있으면 사용
    - 반환: 최대 top_k개의 URL 문자열 리스트
    """

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.brave_key: str = os.getenv("BRAVE_API_KEY", "")
        self.serpapi_key: str = os.getenv("SERPAPI_API_KEY", "")

    def search(self, query: str, top_k: int = 5) -> List[str]:
        try:
            if self.brave_key:
                return self._search_brave(query, top_k)
            if self.serpapi_key:
                return self._search_serpapi(query, top_k)
            return []
        except Exception as e:
            logger.warning("WebSearchMCP failed for %s: %s", query, e)
            return []

    def _search_brave(self, query: str, top_k: int) -> List[str]:
        # Brave Search API (GET https://api.search.brave.com/res/v1/web/search?q=...)
        # 정부기관 우선 검색을 위해 쿼리 개선
        gov_query = f"{query} site:go.kr OR site:gov OR site:ac.kr OR site:re.kr"
        headers = {"Accept": "application/json", "X-Subscription-Token": self.brave_key}

        # 1순위: 정부기관 검색 (더 많은 결과 요청)
        params = {"q": gov_query, "count": max(1, min(top_k * 2, 20))}
        try:
            r = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params=params,
                timeout=self.timeout,
                verify=True,
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("web", {}).get("results", [])
            gov_urls = [item.get("url", "") for item in results if item.get("url")]

            # 정부기관 도메인 우선순위 정렬
            gov_urls = self._prioritize_gov_domains(gov_urls)

            if len(gov_urls) >= top_k:
                return gov_urls[:top_k]
        except Exception as e:
            logger.warning(f"Government site search failed, falling back to general search: {e}")

        # 2순위: 일반 검색 (정부기관 결과가 부족할 때)
        params = {"q": query, "count": max(1, min(top_k * 2, 20))}
        r = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=self.timeout,
            verify=True,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("web", {}).get("results", [])
        all_urls = [item.get("url", "") for item in results if item.get("url")]

        # 정부기관 우선 정렬
        prioritized_urls = self._prioritize_gov_domains(all_urls)
        return prioritized_urls[:top_k]

    def _prioritize_gov_domains(self, urls: List[str]) -> List[str]:
        """정부기관 도메인을 우선순위로 정렬"""
        # 정부기관 도메인 목록 (우선순위 순)
        gov_domains = [
            ".go.kr",  # 정부기관
            ".gov",  # 미국 정부기관
            "kicce.re.kr",  # 육아정책연구소
            "mohw.go.kr",  # 보건복지부
            "nile.or.kr",  # 국가평생교육진흥원
            ".ac.kr",  # 대학
            ".re.kr",  # 연구소
            ".or.kr",  # 기관
        ]

        gov_urls = []
        other_urls = []

        for url in urls:
            url_lower = url.lower()
            is_gov = any(domain in url_lower for domain in gov_domains)
            if is_gov:
                gov_urls.append(url)
            else:
                other_urls.append(url)

        # 정부기관 URL이 있으면 로깅
        if gov_urls:
            logger.info(f"Government sites found: {len(gov_urls)}/{len(urls)} URLs")
            logger.info(f"Government URLs: {gov_urls[:3]}")

        # 정부기관 URL을 먼저, 그 다음 일반 URL
        prioritized = gov_urls + other_urls
        return prioritized

    def _search_serpapi(self, query: str, top_k: int) -> List[str]:
        # SerpAPI (Google) https://serpapi.com/search.json?q=...&api_key=...
        # 정부기관 우선 검색
        gov_query = f"{query} site:go.kr OR site:gov OR site:ac.kr OR site:re.kr"

        # 1순위: 정부기관 검색
        params = {"q": gov_query, "api_key": self.serpapi_key, "num": max(1, min(top_k * 2, 20))}
        try:
            r = requests.get(
                "https://serpapi.com/search.json", params=params, timeout=self.timeout, verify=True
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("organic_results", [])
            gov_urls = []
            for item in results:
                link = item.get("link") or item.get("url")
                if link:
                    gov_urls.append(link)

            # 정부기관 도메인 우선순위 정렬
            gov_urls = self._prioritize_gov_domains(gov_urls)

            if len(gov_urls) >= top_k:
                return gov_urls[:top_k]
        except Exception as e:
            logger.warning(f"Government site search failed, falling back to general search: {e}")

        # 2순위: 일반 검색
        params = {"q": query, "api_key": self.serpapi_key, "num": max(1, min(top_k * 2, 20))}
        r = requests.get(
            "https://serpapi.com/search.json", params=params, timeout=self.timeout, verify=True
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("organic_results", [])
        all_urls = []
        for item in results:
            link = item.get("link") or item.get("url")
            if link:
                all_urls.append(link)

        # 정부기관 우선 정렬
        prioritized_urls = self._prioritize_gov_domains(all_urls)
        return prioritized_urls[:top_k]


class YouTubeMCP:
    """YouTube Data API v3 MCP 서버

    YouTube 채널의 영상 리스트 및 메타데이터를 가져오는 MCP 클라이언트
    - YouTube Data API v3 사용 (공식 API)
    - 채널 ID 또는 사용자명으로 검색
    - 최신 영상, 인기 영상, 검색 결과 제공
    """

    def __init__(
        self, api_key: Optional[str] = None, timeout: float = 10.0, enable_analyzer: bool = True
    ):
        """
        Args:
            api_key: YouTube Data API v3 키 (없으면 환경 변수에서 로드)
            timeout: 요청 타임아웃 (초)
            enable_analyzer: YouTube Analyzer 활성화 여부 (자막 다운로드 등)
        """
        self.timeout = timeout
        self.youtube = None
        self.analyzer = None

        # YouTube Analyzer 초기화 (선택적)
        if enable_analyzer:
            try:
                from src.youtube_analyzer import YouTubeAnalyzer

                self.analyzer = YouTubeAnalyzer()
                logger.info("YouTubeMCP: YouTube Analyzer enabled")
            except ImportError:
                logger.debug("YouTubeMCP: YouTube Analyzer not available (yt-dlp required)")
                self.analyzer = None

        # API 키 가져오기
        if not api_key:
            api_key = os.getenv("YOUTUBE_API_KEY", "")

        if not api_key:
            logger.warning(
                "YouTubeMCP: No API key provided. Set YOUTUBE_API_KEY environment variable."
            )
            return

        try:
            from googleapiclient.discovery import build  # type: ignore

            self.youtube = build("youtube", "v3", developerKey=api_key)
            logger.info("YouTubeMCP: Initialized with API key")
        except ImportError as e:
            logger.error(
                f"YouTubeMCP: google-api-python-client not installed. Install with: pip install google-api-python-client. Error: {e}"
            )
            self.youtube = None
        except Exception as e:
            logger.error(f"YouTubeMCP: Failed to initialize: {e}", exc_info=True)
            self.youtube = None

    def get_channel_videos(
        self,
        channel_id: Optional[str] = None,
        channel_username: Optional[str] = None,
        max_results: int = 10,
        order: str = "date",  # date, rating, relevance, title, videoCount, viewCount
    ) -> List[Dict[str, Any]]:
        """채널의 영상 리스트 가져오기

        Args:
            channel_id: 채널 ID (예: UCxxxx)
            channel_username: 채널 사용자명 (channel_id가 없을 때 사용)
            max_results: 최대 결과 수 (기본값: 10, 최대: 50)
            order: 정렬 순서 (date, rating, relevance, title, videoCount, viewCount)

        Returns:
            List[Dict]: 영상 정보 리스트
        """
        if not self.youtube:
            logger.error("YouTubeMCP: YouTube client not initialized")
            return []

        try:
            # 채널 ID가 없으면 사용자명 또는 핸들로 찾기
            if not channel_id:
                if channel_username:
                    # 사용자명이 @로 시작하면 핸들로 처리
                    if channel_username.startswith("@"):
                        channel_id = self._get_channel_id_by_handle(channel_username)
                    else:
                        channel_id = self._get_channel_id_by_username(channel_username)
                    if not channel_id:
                        logger.warning(
                            f"YouTubeMCP: Channel not found for username/handle: {channel_username}"
                        )
                        return []

            if not channel_id:
                logger.error("YouTubeMCP: channel_id or channel_username is required")
                return []

            # 채널 정보 및 업로드 플레이리스트 ID 가져오기
            channel_info = self._get_channel_info(channel_id)
            if not channel_info:
                logger.error(f"YouTubeMCP: Failed to get channel info for: {channel_id}")
                return []

            playlist_id = channel_info.get("uploads_playlist_id")
            if not playlist_id:
                logger.error(f"YouTubeMCP: No uploads playlist found for channel: {channel_id}")
                return []

            # 플레이리스트에서 영상 리스트 가져오기
            videos = self._get_playlist_videos(playlist_id, max_results, order)

            # 각 영상의 상세 정보 가져오기
            video_ids = [v["video_id"] for v in videos]
            if video_ids:
                video_details = self._get_video_details(video_ids)
                # 상세 정보 병합
                for video in videos:
                    video_id = video["video_id"]
                    if video_id in video_details:
                        video.update(video_details[video_id])

            logger.info(f"YouTubeMCP: Retrieved {len(videos)} videos from channel: {channel_id}")
            return videos

        except Exception as e:
            logger.error(f"YouTubeMCP: Failed to get channel videos: {e}", exc_info=True)
            return []

    def search_videos(
        self,
        query: str,
        max_results: int = 10,
        channel_id: Optional[str] = None,
        order: str = "relevance",  # date, rating, relevance, title, videoCount, viewCount
    ) -> List[Dict[str, Any]]:
        """YouTube에서 영상 검색

        Args:
            query: 검색 쿼리
            max_results: 최대 결과 수
            channel_id: 특정 채널로 제한 (선택적)
            order: 정렬 순서

        Returns:
            List[Dict]: 검색 결과 영상 리스트
        """
        if not self.youtube:
            logger.error("YouTubeMCP: YouTube client not initialized")
            return []

        try:
            videos: List[Dict[str, Any]] = []
            next_page_token = None

            while len(videos) < max_results:
                request_params = {
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": min(50, max_results - len(videos)),
                    "order": order,
                }

                if channel_id:
                    request_params["channelId"] = channel_id

                if next_page_token:
                    request_params["pageToken"] = next_page_token

                request = self.youtube.search().list(**request_params)
                response = request.execute()

                for item in response.get("items", []):
                    video_id = item["id"]["videoId"]
                    snippet = item.get("snippet", {})

                    video_info = {
                        "video_id": video_id,
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                        "published_at": snippet.get("publishedAt", ""),
                        "video_url": f"https://www.youtube.com/watch?v={video_id}",
                        "channel_title": snippet.get("channelTitle", ""),
                        "channel_id": snippet.get("channelId", ""),
                    }

                    videos.append(video_info)

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

            # 상세 정보 가져오기
            video_ids = [v["video_id"] for v in videos]
            if video_ids:
                video_details = self._get_video_details(video_ids)
                for video in videos:
                    video_id = video["video_id"]
                    if video_id in video_details:
                        video.update(video_details[video_id])

            logger.info(f"YouTubeMCP: Found {len(videos)} videos for query: '{query}'")
            return videos[:max_results]

        except Exception as e:
            logger.error(f"YouTubeMCP: Search failed: {e}", exc_info=True)
            return []

    def _get_channel_id_by_handle(self, handle: str) -> str:
        """채널 핸들(@handle)로 채널 ID 찾기"""
        if not self.youtube:
            return ""

        try:
            # @ 기호 제거
            handle_clean = handle.lstrip("@")

            # 최신 API: forHandle 파라미터 사용 (YouTube Data API v3)
            try:
                request = self.youtube.channels().list(part="id", forHandle=handle_clean)
                response = request.execute()

                if response.get("items"):
                    channel_id = response["items"][0]["id"]
                    logger.info(
                        f"YouTubeMCP: Found channel ID {channel_id} for handle @{handle_clean}"
                    )
                    return channel_id
            except Exception as handle_error:
                logger.debug(f"YouTubeMCP: forHandle failed, trying search API: {handle_error}")

            # 대체 방법: search API를 사용하여 채널 찾기
            try:
                search_request = self.youtube.search().list(
                    part="snippet", q=handle_clean, type="channel", maxResults=1
                )
                search_response = search_request.execute()

                if search_response.get("items"):
                    channel_id = search_response["items"][0]["id"]["channelId"]
                    logger.info(
                        f"YouTubeMCP: Found channel ID {channel_id} for handle @{handle_clean} via search"
                    )
                    return channel_id
            except Exception as search_error:
                logger.debug(f"YouTubeMCP: Search API also failed: {search_error}")

            return ""
        except Exception as e:
            logger.error(f"YouTubeMCP: Failed to get channel ID by handle: {e}")
            return ""

    def _get_channel_id_by_username(self, username: str) -> str:
        """사용자명으로 채널 ID 찾기 (레거시 지원)"""
        if not self.youtube:
            return ""

        try:
            request = self.youtube.channels().list(part="id", forUsername=username)
            response = request.execute()

            if response.get("items"):
                return response["items"][0]["id"]
            return ""
        except Exception as e:
            logger.debug(f"YouTubeMCP: Failed to get channel ID by username (legacy): {e}")
            return ""

    def _get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """채널 정보 가져오기"""
        if not self.youtube:
            return {}

        try:
            request = self.youtube.channels().list(
                part="snippet,contentDetails,statistics", id=channel_id
            )
            response = request.execute()

            if not response.get("items"):
                return {}

            item = response["items"][0]
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            statistics = item.get("statistics", {})

            return {
                "id": channel_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "uploads_playlist_id": content_details.get("relatedPlaylists", {}).get(
                    "uploads", ""
                ),
                "subscriber_count": statistics.get("subscriberCount", "0"),
                "video_count": statistics.get("videoCount", "0"),
                "view_count": statistics.get("viewCount", "0"),
            }
        except Exception as e:
            logger.error(f"YouTubeMCP: Failed to get channel info: {e}")
            return {}

    def _get_playlist_videos(
        self, playlist_id: str, max_results: int = 10, order: str = "date"
    ) -> List[Dict[str, Any]]:
        """플레이리스트에서 영상 리스트 가져오기

        Note: playlistItems().list() API는 order 파라미터를 지원하지 않으므로,
        결과를 가져온 후 Python에서 정렬합니다.
        """
        if not self.youtube:
            return []

        videos: List[Dict[str, Any]] = []
        next_page_token = None

        try:
            while len(videos) < max_results:
                request_params = {
                    "part": "snippet",
                    "playlistId": playlist_id,
                    "maxResults": min(50, max_results - len(videos)),
                    # Note: playlistItems().list()는 order 파라미터를 지원하지 않음
                }

                if next_page_token:
                    request_params["pageToken"] = next_page_token

                request = self.youtube.playlistItems().list(**request_params)
                response = request.execute()

                for item in response.get("items", []):
                    snippet = item.get("snippet", {})
                    video_id = snippet.get("resourceId", {}).get("videoId")

                    if not video_id:
                        continue

                    video_info = {
                        "video_id": video_id,
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                        "published_at": snippet.get("publishedAt", ""),
                        "video_url": f"https://www.youtube.com/watch?v={video_id}",
                        "channel_title": snippet.get("channelTitle", ""),
                        "playlist_id": playlist_id,
                    }

                    videos.append(video_info)

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

            # order 파라미터에 따라 정렬 (playlistItems는 기본적으로 업로드 순서로 반환)
            if order == "date":
                # publishedAt 기준으로 내림차순 정렬 (최신순)
                videos.sort(key=lambda x: x.get("published_at", ""), reverse=True)
            elif order == "title":
                # 제목 기준으로 정렬
                videos.sort(key=lambda x: x.get("title", "").lower())
            # 다른 order 값은 기본 순서 유지

            return videos[:max_results]

        except Exception as e:
            logger.error(f"YouTubeMCP: Failed to get playlist videos: {e}", exc_info=True)
            return []

    def _extract_chapters_from_description(self, description: str) -> List[Dict[str, Any]]:
        """YouTube 영상 description에서 책갈피(타임스탬프) 추출

        지원하는 형식:
        - 0:00 소개
        - 1:23 본론
        - 00:00:00 소개
        - 00:01:23 본론
        - 5분 30초 결론
        - [0:00] 소개
        - (1:23) 본론
        - Chapter 1: 0:00 소개
        - 1. 0:00 소개
        """
        chapters: List[Dict[str, Any]] = []

        if not description:
            return chapters

        lines = description.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 패턴 1: [HH:]MM:SS 형식 (다양한 구분자 지원)
            # 예: 0:00, 1:23, 00:01:23, [0:00], (1:23), Chapter 1: 0:00
            patterns = [
                r"\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\]?\s+(.+)",  # [0:00] 또는 0:00
                r"\((\d{1,2}):(\d{2})(?::(\d{2}))?\)\s+(.+)",  # (1:23)
                r"Chapter\s+\d+:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s+(.+)",  # Chapter 1: 0:00
                r"\d+\.\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s+(.+)",  # 1. 0:00
                r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s+(.+)",  # 기본 형식
            ]

            for pattern in patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) == 4:  # HH:MM:SS 형식
                        hours = 0
                        minutes = int(groups[0])
                        seconds = int(groups[1])
                        if groups[2]:  # HH:MM:SS 형식
                            hours = minutes
                            minutes = seconds
                            seconds = int(groups[2])
                        title = groups[3].strip()
                    elif len(groups) == 3:  # MM:SS 형식
                        hours = 0
                        minutes = int(groups[0])
                        seconds = int(groups[1])
                        title = groups[2].strip()
                    else:
                        continue

                    total_seconds = hours * 3600 + minutes * 60 + seconds
                    chapters.append(
                        {
                            "timestamp": total_seconds,
                            "timecode": (
                                f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                                if hours > 0
                                else f"{minutes:02d}:{seconds:02d}"
                            ),
                            "title": title,
                            "source": "description",
                        }
                    )
                    break

            # 패턴 2: 한글 형식 (N분 M초)
            match = re.match(r"(\d+)분\s+(\d+)초\s+(.+)", line)
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                title = match.group(3).strip()

                total_seconds = minutes * 60 + seconds
                chapters.append(
                    {
                        "timestamp": total_seconds,
                        "timecode": f"{minutes:02d}:{seconds:02d}",
                        "title": title,
                        "source": "description",
                    }
                )

        # 중복 제거 및 정렬
        seen = set()
        unique_chapters = []
        for chapter in sorted(chapters, key=lambda x: x["timestamp"]):
            key = (chapter["timestamp"], chapter["title"][:50])  # 타임스탬프와 제목으로 중복 체크
            if key not in seen:
                seen.add(key)
                unique_chapters.append(chapter)

        return unique_chapters

    def _get_video_details(self, video_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """영상 상세 정보 가져오기 (조회수, 좋아요, 댓글 수, 책갈피 등)"""
        if not self.youtube or not video_ids:
            return {}

        try:
            all_details = {}
            # API는 최대 50개씩 처리
            for i in range(0, len(video_ids), 50):
                batch = video_ids[i : i + 50]

                request = self.youtube.videos().list(
                    part="statistics,contentDetails,snippet,topicDetails", id=",".join(batch)
                )
                response = request.execute()

                for item in response.get("items", []):
                    video_id = item["id"]
                    statistics = item.get("statistics", {})
                    content_details = item.get("contentDetails", {})
                    snippet = item.get("snippet", {})

                    description = snippet.get("description", "")
                    topic_details = item.get("topicDetails", {})

                    # 책갈피 추출
                    chapters = self._extract_chapters_from_description(description)

                    # 참여도 계산 (좋아요/조회수 비율)
                    view_count = int(statistics.get("viewCount", 0))
                    like_count = int(statistics.get("likeCount", 0))
                    comment_count = int(statistics.get("commentCount", 0))
                    engagement_rate = (
                        (like_count + comment_count) / view_count if view_count > 0 else 0
                    )

                    all_details[video_id] = {
                        "title": snippet.get("title", ""),
                        "description": description,
                        "description_length": len(description),
                        "view_count": view_count,
                        "like_count": like_count,
                        "comment_count": comment_count,
                        "engagement_rate": round(engagement_rate, 4),
                        "duration": content_details.get("duration", ""),  # ISO 8601 format
                        "tags": snippet.get("tags", []),
                        "category_id": snippet.get("categoryId", ""),
                        "default_language": snippet.get("defaultLanguage", ""),
                        "default_audio_language": snippet.get("defaultAudioLanguage", ""),
                        "topics": topic_details.get("topicIds", []),  # 주제 태그
                        "relevant_topic_ids": topic_details.get("relevantTopicIds", []),
                        "chapters": chapters,  # 책갈피 정보
                        "chapter_count": len(chapters),
                        "has_chapters": len(chapters) > 0,
                        "published_at": snippet.get("publishedAt", ""),
                        "channel_title": snippet.get("channelTitle", ""),
                        "channel_id": snippet.get("channelId", ""),
                        "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    }

            return all_details

        except Exception as e:
            logger.error(f"YouTubeMCP: Failed to get video details: {e}")
            return {}

    async def fetch_for_rag(
        self, user_context: Optional[Dict[str, Any]] = None, channel_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """RAG 파이프라인을 위한 YouTube 데이터 가져오기

        Args:
            user_context: 사용자 컨텍스트 (processed_query 포함 가능)
            channel_id: 채널 ID (없으면 설정에서 가져옴)

        Returns:
            Dict[str, Any]: YouTube 영상 데이터 또는 None
        """
        import asyncio

        youtube_api_key = os.getenv("YOUTUBE_API_KEY", "")
        youtube_channel_id_env = os.getenv("YOUTUBE_CHANNEL_ID", "")
        youtube_channel_handle = os.getenv("YOUTUBE_CHANNEL_HANDLE", "")

        # YouTube API 키가 없으면 스킵
        if not youtube_api_key:
            return None

        # YouTube 클라이언트가 초기화되지 않았으면 스킵
        if not self.youtube:
            logger.debug("YouTubeMCP: YouTube client not initialized, skipping")
            return None

        # 채널 ID 또는 핸들 가져오기
        target_channel_id = channel_id or youtube_channel_id_env
        channel_handle = youtube_channel_handle

        # 채널 ID가 없고 핸들이 있으면 핸들로 채널 ID 찾기
        if not target_channel_id and channel_handle:
            handle_clean = channel_handle.lstrip("@")
            found_channel_id = self._get_channel_id_by_handle(handle_clean)
            if found_channel_id:
                target_channel_id = found_channel_id
                logger.info(
                    f"YouTubeMCP: Resolved channel handle @{handle_clean} to channel ID {target_channel_id}"
                )
            else:
                logger.warning(
                    f"YouTubeMCP: Failed to resolve channel handle @{handle_clean} to channel ID"
                )

        # 쿼리 가져오기
        query = user_context.get("processed_query", "") if user_context else ""
        if not query:
            return None

        # 채널 ID가 설정되어 있으면 항상 해당 채널에서 검색 (키워드 체크 없이)
        if target_channel_id:
            try:
                # 채널 내에서 쿼리로 검색
                videos = await asyncio.to_thread(
                    self.search_videos, query=query, channel_id=target_channel_id, max_results=5
                )

                if videos:
                    logger.info(
                        f"YouTubeMCP: Fetched {len(videos)} videos from channel {target_channel_id} for query: {query}"
                    )
                    # 채널 정보 가져오기
                    channel_info = self._get_channel_info(target_channel_id)
                    return {
                        "videos": videos,
                        "channel_id": target_channel_id,
                        "channel_info": channel_info,
                        "source": "channel_search",
                    }
                else:
                    logger.info(
                        f"YouTubeMCP: No videos found in channel {target_channel_id} for query: {query}, fetching latest videos"
                    )
                    # 쿼리로 검색했을 때 결과가 없으면 최신 영상 가져오기 (사용자가 질의를 했으면 반드시 영상 제공)
                    try:
                        # 최신 영상 가져오기
                        latest_videos = await asyncio.to_thread(
                            self.get_channel_videos,
                            channel_id=target_channel_id,
                            max_results=5,  # 최신 영상 5개 가져오기
                            order="date",
                        )
                        if latest_videos:
                            logger.info(
                                f"YouTubeMCP: Fetched {len(latest_videos)} latest videos from channel {target_channel_id}"
                            )
                            channel_info = self._get_channel_info(target_channel_id)
                            return {
                                "videos": latest_videos,
                                "channel_id": target_channel_id,
                                "channel_info": channel_info,
                                "source": "channel_latest",
                            }
                        else:
                            logger.warning(
                                f"YouTubeMCP: No videos available in channel {target_channel_id}"
                            )
                    except Exception as e2:
                        logger.error(
                            f"YouTubeMCP: Failed to get latest videos: {e2}", exc_info=True
                        )
            except Exception as e:
                logger.warning(f"YouTubeMCP: Failed to search channel videos: {e}")

        # 채널 ID가 없으면 YouTube 관련 키워드가 있을 때만 일반 검색
        youtube_keywords = [
            "유튜브",
            "youtube",
            "영상",
            "동영상",
            "비디오",
            "video",
            "펭수",
            "펭",
            "채널",
            "channel",
            "놀이",
            "배우",
            "시청",
            "콘텐츠",
            "content",
            "미디어",
            "media",
            "강의",
            "교육영상",
        ]

        query_lower = query.lower()
        has_youtube_keyword = any(keyword in query_lower for keyword in youtube_keywords)

        if has_youtube_keyword:
            try:
                # search_videos는 동기 함수이므로 asyncio.to_thread로 실행
                videos = await asyncio.to_thread(self.search_videos, query=query, max_results=5)
                if videos:
                    logger.info(f"YouTubeMCP: Fetched {len(videos)} videos for query: {query}")
                    return {"videos": videos, "query": query, "source": "search"}
            except Exception as e:
                logger.warning(f"YouTubeMCP: Failed to search videos: {e}")
        else:
            logger.debug(
                f"YouTubeMCP: No YouTube-related keywords in query and no channel ID set: {query}"
            )

        return None


# 최신 LangGraph MCP 어댑터 통합(옵션)
try:
    from langchain_mcp_adapters.client import MultiServerMCPClient  # type: ignore
    from langgraph.prebuilt import ToolNode  # type: ignore

    MCP_LIB_AVAILABLE = True
except Exception:
    MCP_LIB_AVAILABLE = False
    ToolNode = object  # type: ignore


async def load_mcp_tools(servers: Dict[str, Dict[str, Any]]) -> List[Any]:
    """MCP 서버 정의로부터 LangChain 호환 도구 목록을 로드.

    servers 예시:
        {
          "math": {"command": "python", "args": ["/abs/path/math_server.py"], "transport": "stdio"},
          "weather": {"url": "http://localhost:8000/mcp", "transport": "streamable_http"}
        }
    """
    if not MCP_LIB_AVAILABLE:
        logger.info("MCP adapters not available. Skipping tool load.")
        return []
    try:
        client = MultiServerMCPClient(servers)  # type: ignore[arg-type]
        tools = await client.get_tools()
        return tools
    except Exception as e:
        logger.warning("Failed to load MCP tools: %s", e)
        return []


async def build_mcp_toolnode(servers: Dict[str, Dict[str, Any]]) -> Optional[Any]:
    """서버 정의에서 도구를 로드해 ToolNode를 생성. 실패 시 None 반환."""
    if not MCP_LIB_AVAILABLE:
        return None
    tools = await load_mcp_tools(servers)
    if not tools:
        return None
    try:
        return ToolNode(tools)  # type: ignore[call-arg]
    except Exception as e:
        logger.warning("Failed to create MCP ToolNode: %s", e)
        return None

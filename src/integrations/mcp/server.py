#!/usr/bin/env python3
"""
MCP Server for Trend Analysis Agents

실전 에이전트 빌더를 위한 MCP 서버 구현
Claude Desktop, Cursor 등에서 트렌드 분석 에이전트를 도구로 사용 가능

Usage:
    python automation/mcp/mcp_server.py

MCP Protocol:
    - tools/list: 사용 가능한 도구 목록 반환
    - tools/call: 도구 실행 및 결과 반환
"""
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/mcp_server.log'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)


def run_news_trend_analysis(query: str, time_window: str = "7d", language: str = "ko", max_results: int = 20) -> Dict[str, Any]:
    """
    뉴스 트렌드 분석 실행
    
    Args:
        query: 검색 쿼리 (예: "전기차", "AI", "비건 식품")
        time_window: 시간 범위 (24h, 7d, 30d)
        language: 언어 코드 (ko, en)
        max_results: 최대 결과 수
        
    Returns:
        분석 결과 딕셔너리
    """
    try:
        from src.agents.news_trend.graph import run_agent
        
        logger.info(f"Running news trend analysis: query={query}, window={time_window}")
        
        result = run_agent(
            query=query,
            time_window=time_window,
            language=language,
            max_results=max_results
        )
        
        # Extract key information (result is NewsAgentState - Pydantic model)
        analysis = getattr(result, 'analysis', {}) if hasattr(result, 'analysis') else {}
        sentiment = analysis.get("sentiment", {}) if isinstance(analysis, dict) else {}
        keywords = analysis.get("keywords", {}) if isinstance(analysis, dict) else {}

        return {
            "success": True,
            "query": query,
            "time_window": time_window,
            "summary": analysis.get("summary", "분석 완료") if isinstance(analysis, dict) else "분석 완료",
            "sentiment": {
                "positive": sentiment.get("positive", 0) if isinstance(sentiment, dict) else 0,
                "neutral": sentiment.get("neutral", 0) if isinstance(sentiment, dict) else 0,
                "negative": sentiment.get("negative", 0) if isinstance(sentiment, dict) else 0,
                "dominant": sentiment.get("dominant", "neutral") if isinstance(sentiment, dict) else "neutral"
            },
            "top_keywords": (keywords.get("top_keywords", [])[:5] if isinstance(keywords, dict) else []),
            "total_items": len(getattr(result, 'normalized', [])),
            "metrics": getattr(result, 'metrics', {}),
            "report_preview": (getattr(result, 'report_md', "")[:500] + "...") if hasattr(result, 'report_md') else "",
            "run_id": getattr(result, 'run_id', None)
        }
        
    except Exception as e:
        logger.error(f"News trend analysis failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


def run_viral_video_analysis(
    query: str,
    market: str = "KR",
    platforms: List[str] = None,
    time_window: str = "24h",
    spike_threshold: float = 2.0
) -> Dict[str, Any]:
    """
    바이럴 비디오 분석 실행
    
    Args:
        query: 검색 쿼리
        market: 시장 코드 (KR, US, JP)
        platforms: 플랫폼 리스트 (youtube, tiktok, instagram)
        time_window: 시간 범위
        spike_threshold: 급상승 임계값 (z-score)
        
    Returns:
        분석 결과 딕셔너리
    """
    if platforms is None:
        platforms = ["youtube"]
    
    try:
        from src.agents.viral_video.graph import run_agent
        
        logger.info(f"Running viral video analysis: query={query}, market={market}, platforms={platforms}")
        
        result = run_agent(
            query=query,
            market=market,
            platforms=platforms,
            time_window=time_window,
            spike_threshold=spike_threshold
        )
        
        # Extract key information (result is a Pydantic model, use attribute access)
        analysis = getattr(result, 'analysis', {})
        viral_data = analysis.get("spikes", {}) if isinstance(analysis, dict) else {}

        # Get top videos
        normalized = getattr(result, 'normalized', [])
        top_videos = []
        for video in normalized[:3]:
            video_dict = video if isinstance(video, dict) else vars(video)
            top_videos.append({
                "title": video_dict.get("title", ""),
                "platform": video_dict.get("platform", ""),
                "views": video_dict.get("views", 0),
                "url": video_dict.get("url", "")
            })

        return {
            "success": True,
            "query": query,
            "market": market,
            "platforms": platforms,
            "spikes_detected": viral_data.get("total_spikes", 0) if isinstance(viral_data, dict) else 0,
            "top_videos": top_videos,
            "success_factors": analysis.get("success_factors", [])[:3] if isinstance(analysis, dict) else [],
            "total_items": len(normalized),
            "metrics": getattr(result, 'metrics', {}),
            "report_preview": (getattr(result, 'report_md', "")[:500] + "...") if hasattr(result, 'report_md') else "",
            "run_id": getattr(result, 'run_id', None)
        }
        
    except Exception as e:
        logger.error(f"Viral video analysis failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


def get_recent_reports(agent_type: str = "all", limit: int = 5) -> Dict[str, Any]:
    """
    최근 생성된 리포트 조회
    
    Args:
        agent_type: 에이전트 타입 (news_trend_agent, viral_video_agent, all)
        limit: 최대 결과 수
        
    Returns:
        리포트 목록
    """
    try:
        artifacts_dir = project_root / "artifacts"
        reports = []
        
        # Determine which directories to search
        if agent_type == "all":
            search_dirs = ["news_trend_agent", "viral_video_agent"]
        else:
            search_dirs = [agent_type]
        
        for agent_dir in search_dirs:
            agent_path = artifacts_dir / agent_dir
            if not agent_path.exists():
                continue
            
            # Find markdown files
            for md_file in sorted(agent_path.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
                reports.append({
                    "agent": agent_dir,
                    "filename": md_file.name,
                    "path": str(md_file),
                    "size": md_file.stat().st_size,
                    "modified": md_file.stat().st_mtime,
                    "preview": md_file.read_text(encoding="utf-8")[:300] + "..."
                })
        
        return {
            "success": True,
            "total": len(reports),
            "reports": reports[:limit]
        }
        
    except Exception as e:
        logger.error(f"Get recent reports failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def get_agent_status() -> Dict[str, Any]:
    """
    에이전트 시스템 상태 조회
    
    Returns:
        시스템 상태 정보
    """
    try:
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Check LLM configuration
        llm_provider = os.getenv("LLM_PROVIDER", "not_set")
        llm_configured = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        
        # Check data source configuration
        news_api_configured = bool(os.getenv("NEWS_API_KEY") or os.getenv("NAVER_CLIENT_ID"))
        video_api_configured = bool(os.getenv("YOUTUBE_API_KEY"))
        
        # Check artifacts directory
        artifacts_dir = project_root / "artifacts"
        total_reports = sum(1 for _ in artifacts_dir.rglob("*.md"))
        
        return {
            "success": True,
            "system": {
                "llm_provider": llm_provider,
                "llm_configured": llm_configured,
                "news_api_configured": news_api_configured,
                "video_api_configured": video_api_configured,
                "fallback_mode": not (news_api_configured or video_api_configured)
            },
            "statistics": {
                "total_reports": total_reports,
                "artifacts_dir": str(artifacts_dir)
            },
            "agents": {
                "news_trend_agent": "operational",
                "viral_video_agent": "operational"
            }
        }
        
    except Exception as e:
        logger.error(f"Get agent status failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# MCP Tool Definitions
# ============================================================================

TOOLS = [
    {
        "name": "analyze_news_trend",
        "description": "뉴스 트렌드를 분석합니다. 감성 분석, 키워드 추출, 인사이트 생성을 수행합니다. 마케팅, 상품기획, 트렌드 리서치에 활용 가능합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "분석할 주제 또는 키워드 (예: '전기차', 'AI', '비건 식품')"
                },
                "time_window": {
                    "type": "string",
                    "description": "분석 기간 (24h: 최근 24시간, 7d: 최근 7일, 30d: 최근 30일)",
                    "enum": ["24h", "7d", "30d"],
                    "default": "7d"
                },
                "language": {
                    "type": "string",
                    "description": "언어 코드 (ko: 한국어, en: 영어)",
                    "enum": ["ko", "en"],
                    "default": "ko"
                },
                "max_results": {
                    "type": "integer",
                    "description": "최대 분석 항목 수 (기본: 20)",
                    "default": 20,
                    "minimum": 5,
                    "maximum": 100
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "analyze_viral_videos",
        "description": "바이럴 비디오를 분석하고 급상승 패턴을 감지합니다. 크리에이터 전략, 콘텐츠 기획, 인플루언서 마케팅에 활용 가능합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색 키워드 (예: 'K-pop', '뷰티', '게임')"
                },
                "market": {
                    "type": "string",
                    "description": "시장 코드 (KR: 한국, US: 미국, JP: 일본)",
                    "enum": ["KR", "US", "JP", "GB", "DE"],
                    "default": "KR"
                },
                "platforms": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["youtube", "tiktok", "instagram"]
                    },
                    "description": "분석할 플랫폼 목록",
                    "default": ["youtube"]
                },
                "time_window": {
                    "type": "string",
                    "description": "분석 기간 (24h, 7d)",
                    "enum": ["24h", "7d"],
                    "default": "24h"
                },
                "spike_threshold": {
                    "type": "number",
                    "description": "급상승 임계값 (z-score, 기본: 2.0, 높을수록 엄격)",
                    "default": 2.0,
                    "minimum": 1.0,
                    "maximum": 5.0
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_recent_reports",
        "description": "최근 생성된 트렌드 분석 리포트를 조회합니다. 과거 분석 결과를 확인하거나 비교할 때 사용합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "description": "에이전트 타입 (all: 전체, news_trend_agent: 뉴스, viral_video_agent: 바이럴)",
                    "enum": ["all", "news_trend_agent", "viral_video_agent"],
                    "default": "all"
                },
                "limit": {
                    "type": "integer",
                    "description": "최대 결과 수 (기본: 5)",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20
                }
            },
            "required": []
        }
    },
    {
        "name": "get_agent_status",
        "description": "에이전트 시스템의 현재 상태를 확인합니다. LLM 설정, API 키 구성, 생성된 리포트 수 등을 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


def handle_call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP 도구 호출 처리
    
    Args:
        tool_name: 도구 이름
        arguments: 도구 인자
        
    Returns:
        실행 결과
    """
    logger.info(f"Tool called: {tool_name} with args: {arguments}")
    
    if tool_name == "analyze_news_trend":
        return run_news_trend_analysis(**arguments)
    elif tool_name == "analyze_viral_videos":
        return run_viral_video_analysis(**arguments)
    elif tool_name == "get_recent_reports":
        return get_recent_reports(**arguments)
    elif tool_name == "get_agent_status":
        return get_agent_status()
    else:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}",
            "available_tools": [t["name"] for t in TOOLS]
        }


def main():
    """
    MCP Server main loop
    
    표준 입력에서 JSON-RPC 메시지를 읽고, 표준 출력으로 응답을 전송합니다.
    """
    logger.info("MCP Trend Analysis Server started")
    logger.info(f"Project root: {project_root}")
    logger.info(f"Available tools: {[t['name'] for t in TOOLS]}")
    
    while True:
        try:
            # Read request from stdin
            line = sys.stdin.readline()
            if not line:
                logger.info("EOF received, shutting down")
                break
            
            line = line.strip()
            if not line:
                continue
            
            # Parse JSON-RPC request
            request = json.loads(line)
            method = request.get("method")
            request_id = request.get("id")
            
            logger.debug(f"Received request: method={method}, id={request_id}")
            
            # Handle different methods
            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": TOOLS
                    }
                }
                
            elif method == "tools/call":
                params = request.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                result = handle_call_tool(tool_name, arguments)
                
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }
                
            elif method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "trend-analysis-agent",
                            "version": "1.0.0"
                        }
                    }
                }
                
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            
            # Send response to stdout
            print(json.dumps(response), flush=True)
            logger.debug(f"Sent response: {response}")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            error_response = {
                "jsonrpc": "2.0",
                "id": request.get("id") if 'request' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()


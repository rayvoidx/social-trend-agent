#!/usr/bin/env python3
"""
AI Trend Analysis Agent - Main Entry Point

OpenAI GPT-5.1를 기본 LLM으로 사용하는 트렌드 분석 에이전트
API 키만 설정하면 즉시 실행 가능
"""
import os
import sys
import argparse
import logging
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_environment():
    """
    환경 변수 검증 및 자동 설정
    
    Returns:
        bool: 환경이 올바르게 설정되었는지 여부
    """
    logger.info("🔍 Validating environment configuration...")
    
    # Load .env file
    env_file = project_root / ".env"
    if not env_file.exists():
        logger.warning("⚠️  .env file not found. Creating from .env.example...")
        env_example = project_root / ".env.example"
        if env_example.exists():
            import shutil
            shutil.copy(env_example, env_file)
            logger.info("✅ .env file created. Please edit it and add your API keys.")
            logger.info(f"📝 Edit: {env_file}")
            return False
        else:
            logger.error("❌ .env.example not found. Cannot create .env file.")
            return False
    
    load_dotenv(env_file, override=True)
    
    # Check LLM configuration
    llm_provider = os.getenv("LLM_PROVIDER", "openai")
    logger.info(f"🤖 LLM Provider: {llm_provider}")
    
    if llm_provider == "openai":
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_key or openai_key.startswith("sk-your-"):
            logger.error("❌ OPENAI_API_KEY is not set or is a placeholder.")
            logger.error("📝 Please edit .env file and add your OpenAI API key:")
            logger.error(f"   {env_file}")
            logger.error("   Get your key at: https://platform.openai.com/api-keys")
            return False
        
        model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-5.1")
        logger.info(f"✅ OpenAI configured: {model_name}")
        logger.info(f"🔑 API Key: {openai_key[:10]}...{openai_key[-4:]}")
        
    elif llm_provider == "azure_openai":
        azure_key = os.getenv("OPENAI_API_KEY", "")
        azure_base = os.getenv("OPENAI_API_BASE", "")
        if not azure_key or not azure_base:
            logger.error("❌ Azure OpenAI configuration incomplete.")
            logger.error("   Required: OPENAI_API_KEY, OPENAI_API_BASE")
            return False
        logger.info(f"✅ Azure OpenAI configured: {azure_base}")
        
    elif llm_provider == "anthropic":
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not anthropic_key:
            logger.error("❌ ANTHROPIC_API_KEY is not set.")
            return False
        logger.info("✅ Anthropic Claude configured")
        
    elif llm_provider == "google":
        google_key = os.getenv("GOOGLE_API_KEY", "")
        if not google_key:
            logger.error("❌ GOOGLE_API_KEY is not set.")
            return False
        logger.info("✅ Google Gemini configured")
        
    elif llm_provider == "ollama":
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        logger.info(f"✅ Ollama configured: {ollama_url}")
        logger.info("ℹ️  Note: Ollama does not require API key")
    
    else:
        logger.error(f"❌ Unknown LLM_PROVIDER: {llm_provider}")
        logger.error("   Supported: openai, azure_openai, anthropic, google, ollama")
        return False
    
    # Check optional data source keys
    news_api_key = os.getenv("NEWS_API_KEY", "")
    naver_client_id = os.getenv("NAVER_CLIENT_ID", "")
    youtube_api_key = os.getenv("YOUTUBE_API_KEY", "")
    
    if not news_api_key and not naver_client_id:
        logger.warning("⚠️  No news API keys found. Using sample data.")
        logger.info("ℹ️  To use real data, add NEWS_API_KEY or NAVER_CLIENT_ID to .env")
    else:
        logger.info("✅ News API configured")
    
    if not youtube_api_key:
        logger.warning("⚠️  YOUTUBE_API_KEY not found. Viral video agent will use sample data.")
    else:
        logger.info("✅ YouTube API configured")
    
    # Check MCP keys (optional)
    brave_api_key = os.getenv("BRAVE_API_KEY", "")
    database_url = os.getenv("DATABASE_URL", "")
    
    if brave_api_key:
        logger.info("✅ Brave Search API configured (for MCP)")
    if database_url:
        logger.info("✅ Database configured (for MCP)")
    
    logger.info("✅ Environment validation completed")
    return True


def run_news_trend_agent(query: str, time_window: str = "7d", language: str = "ko", max_results: int = 20):
    """
    뉴스 트렌드 에이전트 실행
    
    Args:
        query: 검색 쿼리
        time_window: 시간 범위 (24h, 7d, 30d)
        language: 언어 (ko, en)
        max_results: 최대 결과 수
    """
    logger.info("🚀 Starting News Trend Agent...")
    logger.info(f"   Query: {query}")
    logger.info(f"   Time Window: {time_window}")
    logger.info(f"   Language: {language}")
    
    # 세션 관리 (CLI 모드)
    from src.infrastructure.session_manager import SessionContext

    try:
        from src.agents.news_trend.graph import run_agent
        
        with SessionContext(mode="cli") as session:
            # 세션 컨텍스트 저장
            session.update_context("query", query)
            session.update_context("time_window", time_window)
            session.update_context("language", language)
            
            result = run_agent(
                query=query,
                time_window=time_window,
                language=language,
                max_results=max_results
            )
            
            logger.info("✅ Analysis completed successfully")
            
            # Display results
            print("\n" + "="*80)
            print("📊 ANALYSIS RESULTS")
            print("="*80)

            # Handle both dict and object result types
            if isinstance(result, dict):
                query = result.get('query', '')
                time_window = result.get('time_window', '')
                language = result.get('language', '')
                normalized = result.get('normalized', [])
                analysis = result.get('analysis', {})
                metrics = result.get('metrics', {})
            else:
                query = result.query
                time_window = result.time_window
                language = result.language
                normalized = result.normalized
                analysis = result.analysis or {}
                metrics = result.metrics or {}

            print(f"\n🔍 Query: {query}")
            print(f"📅 Time Window: {time_window}")
            print(f"🌐 Language: {language}")
            print(f"📰 Items Analyzed: {len(normalized)}")

            # Sentiment analysis
            sentiment = analysis.get('sentiment', {}) if isinstance(analysis, dict) else {}
            print("\n💭 Sentiment Analysis:")
            print(f"   Positive: {sentiment.get('positive', 0)} ({sentiment.get('positive_pct', 0):.1f}%)")
            print(f"   Neutral:  {sentiment.get('neutral', 0)} ({sentiment.get('neutral_pct', 0):.1f}%)")
            print(f"   Negative: {sentiment.get('negative', 0)} ({sentiment.get('negative_pct', 0):.1f}%)")

            # Keywords
            keywords_data = analysis.get('keywords', {}) if isinstance(analysis, dict) else {}
            keywords = keywords_data.get('top_keywords', []) if isinstance(keywords_data, dict) else []
            if keywords:
                print("\n🔑 Top Keywords:")
                for i, kw in enumerate(keywords[:5], 1):
                    print(f"   {i}. {kw['keyword']} ({kw['count']} times)")

            # Summary
            summary = analysis.get('summary', '') if isinstance(analysis, dict) else ''
            if summary:
                print("\n💡 Summary:")
                print(f"   {summary[:200]}...")
            if metrics:
                print("\n📈 Quality Metrics:")
                print(f"   Coverage: {metrics.get('coverage', 0):.2f}")
                print(f"   Factuality: {metrics.get('factuality', 0):.2f}")
                print(f"   Actionability: {metrics.get('actionability', 0):.2f}")

            # Report file
            if isinstance(result, dict):
                run_id = result.get('run_id', '')
            else:
                run_id = result.run_id
            if run_id:
                report_file = project_root / "artifacts" / "news_trend_agent" / f"{run_id}.md"
                metrics_file = project_root / "artifacts" / "news_trend_agent" / f"{run_id}_metrics.json"
                print(f"\n📄 Full Report: {report_file}")
                print(f"📊 Metrics JSON: {metrics_file}")
            
            print("\n" + "="*80)
            
            return result
        
    except Exception as e:
        logger.error(f"❌ Error running news trend agent: {e}", exc_info=True)
        raise


def run_viral_video_agent(query: str, market: str = "KR", platforms: Optional[list] = None,
                          time_window: str = "24h", spike_threshold: float = 2.0):
    """
    바이럴 비디오 에이전트 실행
    
    Args:
        query: 검색 쿼리
        market: 시장 코드 (KR, US, JP)
        platforms: 플랫폼 리스트 (youtube, tiktok, instagram)
        time_window: 시간 범위
        spike_threshold: 급상승 임계값
    """
    if platforms is None:
        platforms = ["youtube"]
    
    logger.info("🚀 Starting Viral Video Agent...")
    logger.info(f"   Query: {query}")
    logger.info(f"   Market: {market}")
    logger.info(f"   Platforms: {platforms}")
    
    try:
        from src.agents.viral_video.graph import run_agent

        result = run_agent(
            query=query,
            market=market,
            platforms=platforms,
            time_window=time_window,
            spike_threshold=spike_threshold
        )
        
        logger.info("✅ Analysis completed successfully")
        
        # Display results
        print("\n" + "="*80)
        print("🔥 VIRAL VIDEO ANALYSIS RESULTS")
        print("="*80)

        print(f"\n🔍 Query: {result.query}")
        print(f"🌏 Market: {result.market}")
        print(f"📱 Platforms: {', '.join(result.platforms)}")
        print(f"📅 Time Window: {result.time_window}")

        # Viral statistics
        analysis = result.analysis or {}
        spikes = analysis.get('spikes', {}) if isinstance(analysis, dict) else {}
        print("\n🔥 Viral Statistics:")
        print(f"   Spikes Detected: {spikes.get('total_spikes', 0) if isinstance(spikes, dict) else 0}")
        print(f"   Total Items Analyzed: {analysis.get('total_items', 0) if isinstance(analysis, dict) else 0}")

        # Top videos
        normalized = result.normalized or []
        if normalized:
            print("\n🏆 Top Videos:")
            for i, video in enumerate(normalized[:3], 1):
                print(f"   {i}. {video.get('title', 'N/A')}")
                print(f"      Views: {video.get('views', 0):,}")
                print(f"      Platform: {video.get('platform', 'N/A')}")
                print(f"      URL: {video.get('url', 'N/A')}")

        # Success factors
        success_factors = analysis.get('success_factors', []) if isinstance(analysis, dict) else []
        if success_factors:
            print("\n✨ Success Factors:")
            for i, factor in enumerate(success_factors[:3], 1):
                print(f"   {i}. {factor}")

        # Report file
        run_id = result.run_id
        if run_id:
            report_file = project_root / "artifacts" / "viral_video_agent" / f"{run_id}.md"
            metrics_file = project_root / "artifacts" / "viral_video_agent" / f"{run_id}_metrics.json"
            print(f"\n📄 Full Report: {report_file}")
            print(f"📊 Metrics JSON: {metrics_file}")
        
        print("\n" + "="*80)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error running viral video agent: {e}", exc_info=True)
        raise


def run_social_trend_agent(query: str, sources: Optional[list] = None,
                           rss_feeds: Optional[list] = None, time_window: str = "7d",
                           language: str = "ko", max_results: int = 50):
    """
    소셜 트렌드 에이전트 실행

    Args:
        query: 검색 쿼리
        sources: 데이터 소스 리스트 (x, instagram, naver_blog, rss)
        rss_feeds: RSS 피드 URL 리스트
        time_window: 시간 범위
        language: 언어 (ko, en)
        max_results: 최대 결과 수
    """
    if sources is None:
        sources = ["x", "instagram", "naver_blog", "rss"]

    logger.info("🚀 Starting Social Trend Agent...")
    logger.info(f"   Query: {query}")
    logger.info(f"   Sources: {sources}")
    logger.info(f"   Time Window: {time_window}")

    try:
        from src.agents.social_trend.graph import run_agent

        result = run_agent(
            query=query,
            sources=sources,
            rss_feeds=rss_feeds,
            time_window=time_window,
            language=language,
            max_results=max_results
        )

        logger.info("✅ Analysis completed successfully")

        # Display results
        print("\n" + "="*80)
        print("📱 SOCIAL TREND ANALYSIS RESULTS")
        print("="*80)

        print(f"\n🔍 Query: {result['query']}")
        print(f"📅 Time Window: {result['time_window']}")
        print(f"🌐 Language: {result['language']}")
        print(f"📊 Items Analyzed: {len(result['normalized'])}")

        # Sentiment analysis
        analysis = result.get('analysis', {})
        sentiment = analysis.get('sentiment', {})
        print("\n💭 Sentiment Analysis:")
        print(f"   Positive: {sentiment.get('positive', 0)} ({sentiment.get('positive_pct', 0):.1f}%)")
        print(f"   Neutral:  {sentiment.get('neutral', 0)} ({sentiment.get('neutral_pct', 0):.1f}%)")
        print(f"   Negative: {sentiment.get('negative', 0)} ({sentiment.get('negative_pct', 0):.1f}%)")

        # Keywords
        keywords_data = analysis.get('keywords', {})
        keywords = keywords_data.get('top_keywords', [])
        if keywords:
            print("\n🔑 Top Keywords:")
            for i, kw in enumerate(keywords[:5], 1):
                print(f"   {i}. {kw['keyword']} ({kw['count']} times)")

        # Summary
        summary = analysis.get('summary', '')
        if summary:
            print("\n💡 Summary:")
            print(f"   {summary}")

        # Metrics
        metrics = result.get('metrics', {})
        if metrics:
            print("\n📈 Quality Metrics:")
            print(f"   Coverage: {metrics.get('coverage', 0):.2f}")
            print(f"   Factuality: {metrics.get('factuality', 0):.2f}")
            print(f"   Actionability: {metrics.get('actionability', 0):.2f}")

        # Report file
        run_id = result.get('run_id')
        if run_id:
            report_file = project_root / "artifacts" / "social_trend_agent" / f"{run_id}.md"
            print(f"\n📄 Full Report: {report_file}")

        print("\n" + "="*80)

        return result

    except Exception as e:
        logger.error(f"❌ Error running social trend agent: {e}", exc_info=True)
        raise


def run_web_stack() -> None:
    """
    대시보드 웹 스택 실행 (백엔드 + Node API + 프론트엔드).

    - FastAPI 대시보드 (8000)
    - Node TypeScript 추천 API (3001)
    - React/Vite 프론트엔드 (5173)
    """
    logger.info("🚀 Starting web dashboard stack (Python API + Node API + Frontend)...")

    processes: List[subprocess.Popen] = []

    try:
        # 1) Python FastAPI 대시보드
        api_cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "src.api.routes.dashboard:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
        processes.append(
            subprocess.Popen(api_cmd, cwd=str(project_root))
        )
        logger.info("✅ Started Python API on http://localhost:8000")

        # 2) Node TypeScript API
        node_api_dir = project_root / "apps" / "node"
        if node_api_dir.exists():
            node_cmd = ["sh", "-c", "npm install && npm run dev"]
            processes.append(
                subprocess.Popen(node_cmd, cwd=str(node_api_dir))
            )
            logger.info("✅ Started Node API on http://localhost:3001")
        else:
            logger.warning("⚠️ apps/node directory not found, skipping Node API startup")

        # 3) Frontend (Vite)
        frontend_dir = project_root / "apps" / "web"
        if frontend_dir.exists():
            fe_cmd = [
                "sh",
                "-c",
                "npm install && npm run dev -- --host 0.0.0.0 --port 5173",
            ]
            processes.append(
                subprocess.Popen(fe_cmd, cwd=str(frontend_dir))
            )
            logger.info("✅ Started frontend on http://localhost:5173")
        else:
            logger.warning("⚠️ apps/web directory not found, skipping frontend startup")

        # 브라우저 자동 오픈
        try:
            webbrowser.open("http://localhost:5173")
            logger.info("🌐 Opened browser at http://localhost:5173")
        except Exception:
            logger.warning("⚠️ Failed to open browser automatically. Please open http://localhost:5173 manually.")

        # 메인 프로세스가 살아있도록 첫 번째 프로세스를 대기
        if processes:
            processes[0].wait()
        else:
            logger.error("❌ No processes started. Check project structure and dependencies.")

    except KeyboardInterrupt:
        logger.info("🛑 Stopping web stack (Ctrl+C received)")
    finally:
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="AI Trend Analysis Agent - OpenAI GPT-5.1 powered trend analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 대시보드 웹 앱 실행 (추천 UI 포함)
  python main.py --mode web

  # News trend analysis (CLI)
  python main.py --mode cli --agent news_trend_agent --query "AI" --window 7d

  # Viral video analysis (CLI)
  python main.py --mode cli --agent viral_video_agent --query "K-pop" --market KR

  # Social trend analysis (CLI)
  python main.py --mode cli --agent social_trend_agent --query "AI" --sources x instagram naver_blog

  # With custom parameters (CLI)
  python main.py --mode cli --agent news_trend_agent --query "전기차" --window 30d --language ko --max-results 50

Environment:
  Set OPENAI_API_KEY in .env file before running.
  Get your key at: https://platform.openai.com/api-keys
        """
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="cli",
        choices=["cli", "web"],
        help="Execution mode: 'cli' for single-run agents, 'web' for full dashboard stack",
    )

    parser.add_argument(
        "--agent",
        type=str,
        choices=["news_trend_agent", "viral_video_agent", "social_trend_agent"],
        help="Agent to run"
    )
    
    parser.add_argument(
        "--query",
        type=str,
        help="Search query"
    )
    
    # News trend agent options
    parser.add_argument(
        "--window",
        type=str,
        default="7d",
        choices=["24h", "7d", "30d"],
        help="Time window for news trend agent (default: 7d)"
    )
    
    parser.add_argument(
        "--language",
        type=str,
        default="ko",
        choices=["ko", "en"],
        help="Language for news trend agent (default: ko)"
    )
    
    parser.add_argument(
        "--max-results",
        type=int,
        default=20,
        help="Maximum results for news trend agent (default: 20)"
    )
    
    # Viral video agent options
    parser.add_argument(
        "--market",
        type=str,
        default="KR",
        choices=["KR", "US", "JP", "GB", "DE"],
        help="Market code for viral video agent (default: KR)"
    )
    
    parser.add_argument(
        "--platform",
        type=str,
        action="append",
        choices=["youtube", "tiktok", "instagram"],
        help="Platform for viral video agent (can specify multiple)"
    )
    
    parser.add_argument(
        "--spike-threshold",
        type=float,
        default=2.0,
        help="Spike detection threshold for viral video agent (default: 2.0)"
    )

    # Social trend agent options
    parser.add_argument(
        "--sources",
        type=str,
        nargs="+",
        choices=["x", "instagram", "naver_blog", "rss"],
        help="Data sources for social trend agent (can specify multiple)"
    )

    parser.add_argument(
        "--rss-feeds",
        type=str,
        nargs="+",
        help="RSS feed URLs for social trend agent (can specify multiple)"
    )

    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip environment validation"
    )
    
    args = parser.parse_args()
    
    if args.mode == "web":
        # 웹 대시보드 모드
        if not args.skip_validation and not validate_environment():
            logger.error("❌ Environment validation failed. Please fix the issues above.")
            sys.exit(1)
        run_web_stack()
        return

    # CLI 에이전트 모드
    if not args.agent or not args.query:
        parser.error("--mode cli requires --agent and --query")

    # Print banner
    print("\n" + "=" * 80)
    print("🤖 AI Trend Analysis Agent")
    print("   Powered by OpenAI GPT-5.1")
    print("=" * 80 + "\n")

    # Validate environment
    if not args.skip_validation:
        if not validate_environment():
            logger.error("❌ Environment validation failed. Please fix the issues above.")
            sys.exit(1)

    # Run agent
    try:
        if args.agent == "news_trend_agent":
            run_news_trend_agent(
                query=args.query,
                time_window=args.window,
                language=args.language,
                max_results=args.max_results,
            )
        elif args.agent == "viral_video_agent":
            platforms = args.platform if args.platform else ["youtube"]
            run_viral_video_agent(
                query=args.query,
                market=args.market,
                platforms=platforms,
                time_window=args.window,
                spike_threshold=args.spike_threshold,
            )
        elif args.agent == "social_trend_agent":
            sources = args.sources if args.sources else ["x", "instagram", "naver_blog", "rss"]
            run_social_trend_agent(
                query=args.query,
                sources=sources,
                rss_feeds=args.rss_feeds,
                time_window=args.window,
                language=args.language,
                max_results=args.max_results,
            )

        logger.info("✅ Agent execution completed successfully")
        sys.exit(0)

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


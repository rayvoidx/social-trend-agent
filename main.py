#!/usr/bin/env python3
"""
AI Trend Analysis Agent - Main Entry Point

OpenAI GPT-5.2를 기본 LLM으로 사용하는 트렌드 분석 에이전트
API 키만 설정하면 즉시 실행 가능
"""
import os
import sys
import argparse
import logging
import subprocess
import webbrowser
import uuid
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.logging import setup_logging, AgentLogger, log_json_line
from src.infrastructure.monitoring.prometheus_metrics import get_metrics_registry

# Setup logging (Default to structured JSON logs)
logger = setup_logging(level=logging.INFO, json_format=True)


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
        logger.warning("⚠️  .env file not found. Creating from .env.template...")
        env_template = project_root / "env.template"
        if env_template.exists():
            import shutil
            shutil.copy(env_template, env_file)
            logger.info("✅ .env file created. Please edit it and add your API keys.")
            logger.info(f"📝 Edit: {env_file}")
            return False
        else:
            logger.error("❌ env.template not found. Cannot create .env file.")
            return False
    
    load_dotenv(env_file, override=True)
    
    # Check LLM configuration (multi-LLM friendly)
    openai_key = os.getenv("OPENAI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    google_key = os.getenv("GOOGLE_API_KEY", "")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "")

    if not any([openai_key, anthropic_key, google_key, ollama_url]):
        logger.error("❌ No LLM configured. Please set at least one of OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, or OLLAMA_BASE_URL.")
        logger.error(f"📝 Edit your .env file: {env_file}")
        return False

    if openai_key and not openai_key.startswith("sk-your-"):
        model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-5.2")
        logger.info(f"✅ OpenAI configured: {model_name}")
        # logger.info(f"🔑 OpenAI Key: {openai_key[:10]}...{openai_key[-4:]}") # Don't log keys

    if anthropic_key:
        logger.info("✅ Anthropic Claude configured")

    if google_key:
        logger.info("✅ Google Gemini configured")

    if ollama_url:
        logger.info(f"✅ Ollama configured: {ollama_url or 'http://localhost:11434'}")
    
    # Check optional data source keys
    # (Checking logic kept simple for brevity)
    
    # Check MCP keys (optional)
    brave_api_key = os.getenv("BRAVE_API_KEY", "")
    supadata_key = os.getenv("SUPADATA_API_KEY", "")
    
    if brave_api_key:
        logger.info("✅ Brave Search API configured (for MCP)")
    if supadata_key:
        logger.info("✅ Supadata API configured (for MCP)")
    
    logger.info("✅ Environment validation completed")
    return True


def run_news_trend_agent(query: str, time_window: str = "7d", language: str = "ko", max_results: int = 20):
    """
    뉴스 트렌드 에이전트 실행
    """
    run_id = str(uuid.uuid4())
    agent_logger = AgentLogger("news_trend_agent", run_id)
    
    agent_logger.info("🚀 Starting News Trend Agent", query=query, time_window=time_window)
    
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
                max_results=max_results,
                run_id=run_id
            )
            
            agent_logger.info("✅ Analysis completed successfully")
            
            # Display results (Human readable)
            print("\n" + "="*80)
            print("📊 ANALYSIS RESULTS")
            print("="*80)

            # Handle both dict and object result types
            if isinstance(result, dict):
                normalized = result.get('normalized', [])
                analysis = result.get('analysis', {})
                metrics = result.get('metrics', {})
            else:
                normalized = result.normalized
                analysis = result.analysis or {}
                metrics = result.metrics or {}

            # ... (Existing print logic omitted for brevity, keeping it simple or reusing)
            summary = analysis.get('summary', '') if isinstance(analysis, dict) else ''
            print(f"\n💡 Summary:\n{summary[:500]}...")
            
            # Report file
            report_file = project_root / "artifacts" / "news_trend_agent" / f"{run_id}.md"
            print(f"\n📄 Full Report: {report_file}")
            
            # Log metrics snapshot
            snapshot = get_metrics_registry().get_snapshot()
            log_json_line({
                "type": "run_summary",
                "run_id": run_id,
                "agent": "news_trend_agent",
                "metrics": snapshot,
                "status": "success"
            })
            
            return result
        
    except Exception as e:
        agent_logger.error(f"❌ Error running news trend agent: {e}", exc_info=True)
        raise


def run_viral_video_agent(query: str, market: str = "KR", platforms: Optional[list] = None,
                          time_window: str = "24h", spike_threshold: float = 2.0):
    """
    바이럴 비디오 에이전트 실행
    """
    if platforms is None:
        platforms = ["youtube"]
    
    run_id = str(uuid.uuid4())
    agent_logger = AgentLogger("viral_video_agent", run_id)
    
    agent_logger.info("🚀 Starting Viral Video Agent", query=query, market=market, platforms=platforms)
    
    try:
        from src.agents.viral_video.graph import run_agent

        result = run_agent(
            query=query,
            market=market,
            platforms=platforms,
            time_window=time_window,
            spike_threshold=spike_threshold,
            run_id=run_id
        )
        
        agent_logger.info("✅ Analysis completed successfully")
        
        # Display results
        print("\n" + "="*80)
        print("🔥 VIRAL VIDEO ANALYSIS RESULTS")
        print("="*80)

        analysis = result.analysis or {}
        spikes = analysis.get('spikes', {}) if isinstance(analysis, dict) else {}
        print(f"\n🔥 Spikes Detected: {spikes.get('total_spikes', 0) if isinstance(spikes, dict) else 0}")
        
        # Report file
        report_file = project_root / "artifacts" / "viral_video_agent" / f"{run_id}.md"
        print(f"\n📄 Full Report: {report_file}")

        # Log metrics snapshot
        snapshot = get_metrics_registry().get_snapshot()
        log_json_line({
            "type": "run_summary",
            "run_id": run_id,
            "agent": "viral_video_agent",
            "metrics": snapshot,
            "status": "success"
        })
        
        return result
        
    except Exception as e:
        agent_logger.error(f"❌ Error running viral video agent: {e}", exc_info=True)
        raise


def run_social_trend_agent(query: str, sources: Optional[list] = None,
                           rss_feeds: Optional[list] = None, time_window: str = "7d",
                           language: str = "ko", max_results: int = 50):
    """
    소셜 트렌드 에이전트 실행
    """
    if sources is None:
        sources = ["x", "instagram", "naver_blog", "rss"]

    run_id = str(uuid.uuid4())
    agent_logger = AgentLogger("social_trend_agent", run_id)
    
    agent_logger.info("🚀 Starting Social Trend Agent", query=query, sources=sources)

    try:
        from src.agents.social_trend.graph import run_agent

        result = run_agent(
            query=query,
            sources=sources,
            rss_feeds=rss_feeds,
            time_window=time_window,
            language=language,
            max_results=max_results,
            run_id=run_id
        )

        agent_logger.info("✅ Analysis completed successfully")

        # Display results
        print("\n" + "="*80)
        print("📱 SOCIAL TREND ANALYSIS RESULTS")
        print("="*80)
        
        # Report file
        report_file = project_root / "artifacts" / "social_trend_agent" / f"{run_id}.md"
        print(f"\n📄 Full Report: {report_file}")

        # Log metrics snapshot
        snapshot = get_metrics_registry().get_snapshot()
        log_json_line({
            "type": "run_summary",
            "run_id": run_id,
            "agent": "social_trend_agent",
            "metrics": snapshot,
            "status": "success"
        })

        return result

    except Exception as e:
        agent_logger.error(f"❌ Error running social trend agent: {e}", exc_info=True)
        raise


def run_web_stack() -> None:
    """
    대시보드 웹 스택 실행
    """
    logger.info("🚀 Starting web dashboard stack...")
    # ... (Keep existing implementation mostly same but use structured logger)
    
    processes: List[subprocess.Popen] = []

    try:
        # 1) Python FastAPI 대시보드
        api_cmd = [
            sys.executable, "-m", "uvicorn", "src.api.routes.dashboard:app",
            "--host", "0.0.0.0", "--port", "8000"
        ]
        processes.append(subprocess.Popen(api_cmd, cwd=str(project_root)))
        logger.info("✅ Started Python API on http://localhost:8000")

        # 2) Node TypeScript API
        node_api_dir = project_root / "apps" / "node"
        if node_api_dir.exists():
            node_cmd = ["sh", "-c", "npm install && npm run dev"]
            processes.append(subprocess.Popen(node_cmd, cwd=str(node_api_dir)))
            logger.info("✅ Started Node API on http://localhost:3001")
        
        # 3) Frontend (Vite)
        frontend_dir = project_root / "apps" / "web"
        if frontend_dir.exists():
            fe_cmd = ["sh", "-c", "npm install && npm run dev -- --host 0.0.0.0 --port 5173"]
            processes.append(subprocess.Popen(fe_cmd, cwd=str(frontend_dir)))
            logger.info("✅ Started frontend on http://localhost:5173")

        # 브라우저 자동 오픈
        try:
            webbrowser.open("http://localhost:5173")
        except Exception:
            pass

        if processes:
            processes[0].wait()
            
    except KeyboardInterrupt:
        logger.info("🛑 Stopping web stack")
    finally:
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="AI Trend Analysis Agent")
    
    parser.add_argument("--mode", type=str, default="cli", choices=["cli", "web"], help="Execution mode")
    parser.add_argument("--agent", type=str, choices=["news_trend_agent", "viral_video_agent", "social_trend_agent"], help="Agent to run")
    parser.add_argument("--query", type=str, help="Search query")
    parser.add_argument("--window", type=str, default="7d", help="Time window")
    parser.add_argument("--language", type=str, default="ko", help="Language")
    parser.add_argument("--max-results", type=int, default=20, help="Max results")
    parser.add_argument("--market", type=str, default="KR", help="Market code")
    parser.add_argument("--platform", type=str, action="append", help="Platform")
    parser.add_argument("--sources", type=str, nargs="+", help="Data sources")
    parser.add_argument("--rss-feeds", type=str, nargs="+", help="RSS feed URLs")
    parser.add_argument("--skip-validation", action="store_true", help="Skip env validation")
    parser.add_argument("--spike-threshold", type=float, default=2.0, help="Spike threshold")
    
    args = parser.parse_args()
    
    if args.mode == "web":
        if not args.skip_validation and not validate_environment():
            sys.exit(1)
        run_web_stack()
        return

    # CLI 에이전트 모드
    if not args.agent or not args.query:
        parser.error("--mode cli requires --agent and --query")

    print("\n" + "=" * 80)
    print("🤖 AI Trend Analysis Agent")
    print("   Powered by OpenAI GPT-5.2")
    print("=" * 80 + "\n")

    if not args.skip_validation and not validate_environment():
        sys.exit(1)

    try:
        if args.agent == "news_trend_agent":
            run_news_trend_agent(args.query, args.window, args.language, args.max_results)
        elif args.agent == "viral_video_agent":
            platforms = args.platform if args.platform else ["youtube"]
            run_viral_video_agent(args.query, args.market, platforms, args.window, args.spike_threshold)
        elif args.agent == "social_trend_agent":
            sources = args.sources if args.sources else ["x", "instagram", "naver_blog", "rss"]
            run_social_trend_agent(args.query, sources, args.rss_feeds, args.window, args.language, args.max_results)

    except KeyboardInterrupt:
        logger.info("⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

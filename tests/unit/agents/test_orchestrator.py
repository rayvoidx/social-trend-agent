"""
Tests for the Orchestrator module.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.orchestrator import (
    SUPPORTED_AGENTS,
    select_agent,
    plan_workflow,
    orchestrate_request,
    _planner_enabled,
    _multi_agent_enabled,
)


class TestSelectAgent:
    """Tests for select_agent routing."""

    def test_explicit_hint_respected(self):
        """When a valid hint is provided, it should be returned directly."""
        with patch("src.agents.orchestrator.route_request") as mock_route:
            agent, routing = select_agent("anything", hint="viral_video_agent")
            assert agent == "viral_video_agent"
            assert routing["notes"] == "explicit_hint"
            mock_route.assert_not_called()

    def test_invalid_hint_falls_through(self):
        """An invalid hint should be ignored and routing should proceed normally."""
        with patch("src.agents.orchestrator.route_request", return_value={}):
            agent, _ = select_agent("latest news trends", hint="invalid_agent")
            assert agent == "news_trend_agent"

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("유튜브 인기 영상 분석", "viral_video_agent"),
            ("youtube trending videos", "viral_video_agent"),
            ("tiktok viral challenge", "viral_video_agent"),
            ("바이럴 콘텐츠 분석", "viral_video_agent"),
            ("shorts 조회수 급상승", "viral_video_agent"),
            ("릴스 인기 영상", "viral_video_agent"),
        ],
    )
    def test_viral_keywords_route_to_viral_agent(self, query, expected):
        with patch("src.agents.orchestrator.route_request", return_value={}):
            agent, _ = select_agent(query)
            assert agent == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("트위터 트렌드 분석", "social_trend_agent"),
            ("twitter trending topics", "social_trend_agent"),
            ("인스타 해시태그 분석", "social_trend_agent"),
            ("instagram influencer analysis", "social_trend_agent"),
            ("블로그 트렌드", "social_trend_agent"),
            ("sns 마케팅 분석", "social_trend_agent"),
            ("소셜 미디어 트렌드", "social_trend_agent"),
            ("커뮤니티 반응 분석", "social_trend_agent"),
        ],
    )
    def test_social_keywords_route_to_social_agent(self, query, expected):
        with patch("src.agents.orchestrator.route_request", return_value={}):
            agent, _ = select_agent(query)
            assert agent == expected

    def test_general_queries_route_to_news_agent(self):
        with patch("src.agents.orchestrator.route_request", return_value={}):
            agent, _ = select_agent("미국 경제 동향 분석")
            assert agent == "news_trend_agent"

    def test_empty_query_defaults_to_news(self):
        with patch("src.agents.orchestrator.route_request", return_value={}):
            agent, _ = select_agent("")
            assert agent == "news_trend_agent"


class TestPlanWorkflow:
    """Tests for plan_workflow planning."""

    def test_fallback_plan_when_planner_disabled(self):
        with (
            patch("src.agents.orchestrator._planner_enabled", return_value=False),
            patch("src.agents.orchestrator.route_request", return_value={}),
        ):
            plan = plan_workflow("test query", routing={})
            assert plan["notes"] == "planner_disabled"
            assert plan["combine"] == "single"
            assert len(plan["agents"]) == 1
            assert plan["agents"][0]["agent_name"] in SUPPORTED_AGENTS

    def test_fallback_plan_structure(self):
        with (
            patch("src.agents.orchestrator._planner_enabled", return_value=False),
            patch("src.agents.orchestrator.route_request", return_value={}),
        ):
            plan = plan_workflow("유튜브 트렌드", routing={})
            assert plan["primary_agent"] == "viral_video_agent"
            steps = plan["agents"][0].get("steps", [])
            assert len(steps) >= 2
            ops = [s["op"] for s in steps]
            assert "collect" in ops
            assert "report" in ops

    def test_fallback_on_llm_exception(self):
        with (
            patch("src.agents.orchestrator._planner_enabled", return_value=True),
            patch("src.agents.orchestrator.route_request", return_value={}),
            patch("src.agents.orchestrator.get_llm_client", side_effect=Exception("LLM down")),
        ):
            plan = plan_workflow("test query", routing={})
            assert plan["notes"] == "planner_fallback"
            assert plan["combine"] == "single"

    def test_step_retry_policies_present(self):
        with (
            patch("src.agents.orchestrator._planner_enabled", return_value=False),
            patch("src.agents.orchestrator.route_request", return_value={}),
        ):
            plan = plan_workflow("news trends", routing={})
            for step in plan["agents"][0].get("steps", []):
                assert "retry_policy" in step
                assert "timeout_seconds" in step
                assert "circuit_breaker" in step


class TestOrchestrateRequest:
    """Tests for orchestrate_request 3-gear orchestration."""

    def test_low_complexity_skips_planner(self):
        with patch(
            "src.agents.orchestrator.route_request",
            return_value={"complexity": "low"},
        ):
            result = orchestrate_request("간단한 뉴스 검색")
            assert "routing" in result
            assert "plan" in result
            assert result["plan"]["notes"] == "router_only"

    def test_medium_complexity_skips_planner(self):
        with patch(
            "src.agents.orchestrator.route_request",
            return_value={"complexity": "medium"},
        ):
            result = orchestrate_request("미국 시장 분석")
            assert result["plan"]["notes"] == "router_only"

    def test_high_complexity_invokes_planner(self):
        with (
            patch(
                "src.agents.orchestrator.route_request",
                return_value={"complexity": "high"},
            ),
            patch("src.agents.orchestrator._planner_enabled", return_value=False),
        ):
            result = orchestrate_request("복합 멀티 에이전트 분석")
            assert result["plan"]["notes"] == "planner_disabled"

    def test_result_contains_routing_and_plan(self):
        with patch(
            "src.agents.orchestrator.route_request",
            return_value={"complexity": "low"},
        ):
            result = orchestrate_request("test")
            assert "routing" in result
            assert "plan" in result
            plan = result["plan"]
            assert "primary_agent" in plan
            assert "agents" in plan
            assert "combine" in plan


class TestConfigFlags:
    """Tests for environment-driven config flags."""

    @pytest.mark.parametrize("val,expected", [("1", True), ("true", True), ("0", False), ("no", False)])
    def test_planner_enabled(self, val, expected):
        with patch.dict("os.environ", {"ORCHESTRATOR_ENABLE_PLANNER": val}):
            assert _planner_enabled() == expected

    @pytest.mark.parametrize("val,expected", [("1", True), ("true", True), ("0", False), ("no", False)])
    def test_multi_agent_enabled(self, val, expected):
        with patch.dict("os.environ", {"ORCHESTRATOR_MULTI_AGENT": val}):
            assert _multi_agent_enabled() == expected

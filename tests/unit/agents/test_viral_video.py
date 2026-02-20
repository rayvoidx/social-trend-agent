"""
Tests for Viral Video Agent graph nodes.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.core.state import ViralAgentState
from src.agents.viral_video.graph import (
    collect_node,
    normalize_node,
    analyze_node,
    report_node,
    build_graph,
)


def _make_state(**overrides) -> ViralAgentState:
    """Helper to create a ViralAgentState with sensible defaults."""
    defaults = {
        "query": "test viral videos",
        "market": "KR",
        "platforms": ["youtube"],
        "time_window": "24h",
        "spike_threshold": 2.0,
        "run_id": "test-run-001",
    }
    defaults.update(overrides)
    return ViralAgentState(**defaults)


class TestCollectNode:
    """Tests for collect_node."""

    def test_collect_returns_raw_items(self):
        state = _make_state(platforms=["youtube"])
        mock_stats = [
            {"video_id": "v1", "title": "Test Video", "views": 1000, "platform": "youtube"}
        ]
        with patch("src.agents.viral_video.graph.fetch_video_stats", return_value=mock_stats):
            result = collect_node(state)
            assert "raw_items" in result
            assert len(result["raw_items"]) == 1
            assert result["raw_items"][0]["video_id"] == "v1"

    def test_collect_multiple_platforms(self):
        state = _make_state(platforms=["youtube", "tiktok"])
        yt_stats = [{"video_id": "yt1", "title": "YT", "views": 100, "platform": "youtube"}]
        tt_stats = [{"video_id": "tt1", "title": "TT", "views": 200, "platform": "tiktok"}]

        def mock_fetch(platform, **kwargs):
            return yt_stats if platform == "youtube" else tt_stats

        with patch("src.agents.viral_video.graph.fetch_video_stats", side_effect=mock_fetch):
            result = collect_node(state)
            assert len(result["raw_items"]) == 2

    def test_collect_handles_empty_results(self):
        state = _make_state(platforms=["youtube"])
        with patch("src.agents.viral_video.graph.fetch_video_stats", return_value=[]):
            result = collect_node(state)
            assert result["raw_items"] == []


class TestNormalizeNode:
    """Tests for normalize_node."""

    def test_normalize_extracts_fields(self):
        state = _make_state(
            raw_items=[
                {
                    "video_id": "v1",
                    "title": "Test",
                    "channel": "Ch1",
                    "views": 5000,
                    "likes": 100,
                    "comments": 50,
                    "published_at": "2025-01-01",
                    "platform": "youtube",
                    "url": "https://youtube.com/v1",
                    "thumbnail": "https://img.youtube.com/v1.jpg",
                    "extra_field": "ignored",
                }
            ]
        )
        result = normalize_node(state)
        assert len(result["normalized"]) == 1
        item = result["normalized"][0]
        assert item["video_id"] == "v1"
        assert item["views"] == 5000
        assert "extra_field" not in item

    def test_normalize_fills_defaults(self):
        state = _make_state(raw_items=[{}])
        result = normalize_node(state)
        item = result["normalized"][0]
        assert item["video_id"] == ""
        assert item["views"] == 0
        assert item["platform"] == "youtube"

    def test_normalize_empty_input(self):
        state = _make_state(raw_items=[])
        result = normalize_node(state)
        assert result["normalized"] == []


class TestAnalyzeNode:
    """Tests for analyze_node."""

    def test_analyze_returns_spikes_and_clusters(self):
        state = _make_state(
            normalized=[
                {"video_id": "v1", "title": "Test", "views": 10000},
                {"video_id": "v2", "title": "Test2", "views": 500},
            ]
        )
        mock_spikes = {"spike_videos": [{"video_id": "v1"}], "threshold": 2.0}
        mock_clusters = {"top_clusters": [{"topic": "tech", "count": 2, "avg_views": 5250}], "total_clusters": 1}

        with (
            patch("src.agents.viral_video.graph.detect_spike", return_value=mock_spikes),
            patch("src.agents.viral_video.graph.topic_cluster", return_value=mock_clusters),
        ):
            result = analyze_node(state)
            assert "analysis" in result
            assert "spikes" in result["analysis"]
            assert "clusters" in result["analysis"]
            assert result["analysis"]["total_items"] == 2


class TestReportNode:
    """Tests for report_node."""

    def test_report_generates_markdown(self):
        state = _make_state(
            normalized=[{"url": "https://youtube.com/v1"}],
            analysis={
                "spikes": {
                    "spike_videos": [
                        {
                            "title": "Viral Hit",
                            "channel": "Creator",
                            "views": 1000000,
                            "likes": 50000,
                            "platform": "youtube",
                            "url": "https://youtube.com/v1",
                            "z_score": 3.5,
                        }
                    ]
                },
                "clusters": {
                    "top_clusters": [
                        {"topic": "Tech", "count": 5, "avg_views": 200000}
                    ]
                },
                "success_factors": "Great thumbnail and title.",
            },
        )
        result = report_node(state)
        assert "report_md" in result
        assert "바이럴 영상 분석 리포트" in result["report_md"]
        assert "Viral Hit" in result["report_md"]
        assert "metrics" in result

    def test_report_empty_spikes(self):
        state = _make_state(
            normalized=[],
            analysis={
                "spikes": {"spike_videos": []},
                "clusters": {"top_clusters": []},
                "success_factors": "N/A",
            },
        )
        result = report_node(state)
        assert "급상승 영상이 발견되지 않았습니다" in result["report_md"]


class TestBuildGraph:
    """Tests for build_graph compilation."""

    def test_graph_compiles_without_error(self):
        graph = build_graph(checkpointer=None)
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        graph = build_graph(checkpointer=None)
        node_names = set(graph.nodes.keys())
        expected = {"router", "collect", "normalize", "analyze", "summarize", "report", "notify"}
        assert expected.issubset(node_names)

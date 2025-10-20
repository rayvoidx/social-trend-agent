"""
Unit tests for viral_video_agent tools
"""
import pytest
import numpy as np
from agents.viral_video_agent.tools import (
    fetch_video_stats,
    detect_spike,
    topic_cluster,
    _get_sample_videos,
    _calculate_z_score
)


class TestFetchVideoStats:
    """Tests for fetch_video_stats function"""

    def test_fetch_with_sample_data(self):
        """Test video stats fetching with sample data"""
        results = fetch_video_stats(
            query="trending",
            platforms=["youtube"],
            market="KR",
            time_window="7d"
        )

        assert isinstance(results, list)
        assert len(results) > 0
        assert all("platform" in item for item in results)
        assert all("video_id" in item for item in results)
        assert all("views" in item for item in results)

    def test_multi_platform_fetch(self):
        """Test multi-platform fetching"""
        results = fetch_video_stats(
            query="K-pop",
            platforms=["youtube", "tiktok"],
            market="KR"
        )

        platforms = [item["platform"] for item in results]
        assert "youtube" in platforms or "tiktok" in platforms

    def test_get_sample_videos(self):
        """Test sample video generation"""
        samples = _get_sample_videos("test", "youtube", "KR")

        assert isinstance(samples, list)
        assert len(samples) > 0
        assert all("platform" in item for item in samples)
        assert all(item["platform"] == "youtube" for item in samples)


class TestDetectSpike:
    """Tests for detect_spike function"""

    def test_spike_detection_with_spike(self):
        """Test spike detection when spike exists"""
        # Create timeseries with clear spike
        timeseries = [
            {"video_id": "v1", "views": 1000, "title": "Normal"},
            {"video_id": "v2", "views": 1100, "title": "Normal"},
            {"video_id": "v3", "views": 5000, "title": "Spike!"},  # Clear spike
        ]

        result = detect_spike(timeseries, threshold=2.0)

        assert "spike_detected" in result
        assert len(result["spike_detected"]) > 0
        assert result["total_spikes"] > 0

    def test_spike_detection_without_spike(self):
        """Test spike detection when no spike exists"""
        # Create uniform timeseries
        timeseries = [
            {"video_id": f"v{i}", "views": 1000 + i*10, "title": "Normal"}
            for i in range(10)
        ]

        result = detect_spike(timeseries, threshold=3.0)

        assert result["total_spikes"] == 0
        assert len(result["spike_detected"]) == 0

    def test_calculate_z_score(self):
        """Test z-score calculation"""
        values = [100, 100, 100, 100, 500]  # Last one is spike
        z_scores = [_calculate_z_score(v, values) for v in values]

        # Last z-score should be significantly higher
        assert z_scores[-1] > z_scores[0]
        assert z_scores[-1] > 2.0  # Clear spike

    def test_empty_timeseries(self):
        """Test spike detection with empty timeseries"""
        result = detect_spike([], threshold=2.0)

        assert result["total_spikes"] == 0
        assert result["spike_detected"] == []

    def test_single_item_timeseries(self):
        """Test spike detection with single item"""
        timeseries = [{"video_id": "v1", "views": 1000, "title": "Test"}]

        result = detect_spike(timeseries, threshold=2.0)

        # Single item cannot have a spike
        assert result["total_spikes"] == 0

    def test_threshold_sensitivity(self):
        """Test different threshold values"""
        timeseries = [
            {"video_id": "v1", "views": 1000, "title": "Normal"},
            {"video_id": "v2", "views": 1100, "title": "Normal"},
            {"video_id": "v3", "views": 2000, "title": "Moderate spike"},
        ]

        # Low threshold - should detect spike
        result_low = detect_spike(timeseries, threshold=1.5)
        # High threshold - might not detect spike
        result_high = detect_spike(timeseries, threshold=3.0)

        assert result_low["total_spikes"] >= result_high["total_spikes"]


class TestTopicCluster:
    """Tests for topic_cluster function"""

    def test_basic_clustering(self):
        """Test basic topic clustering"""
        texts = [
            "K-pop dance challenge trending",
            "K-pop music video released",
            "Dance cover tutorial popular",
            "Tutorial for beginners"
        ]

        result = topic_cluster(texts, n_clusters=2)

        assert "clusters" in result
        assert len(result["clusters"]) <= 2
        assert all("keywords" in cluster for cluster in result["clusters"])

    def test_single_cluster(self):
        """Test with single cluster"""
        texts = ["similar text", "very similar text", "almost same text"]

        result = topic_cluster(texts, n_clusters=1)

        assert len(result["clusters"]) == 1

    def test_empty_texts(self):
        """Test clustering with empty texts"""
        result = topic_cluster([], n_clusters=3)

        assert result["clusters"] == []

    def test_insufficient_texts(self):
        """Test clustering with fewer texts than clusters"""
        texts = ["text 1", "text 2"]

        result = topic_cluster(texts, n_clusters=5)

        # Should return at most 2 clusters
        assert len(result["clusters"]) <= 2


class TestAnalyzeSuccessFactors:
    """Tests for success factor analysis"""

    def test_success_factor_structure(self):
        """Test success factor analysis structure"""
        from agents.viral_video_agent.tools import analyze_success_factors

        video = {
            "video_id": "test123",
            "title": "Amazing New Product Review!",
            "thumbnail": "https://example.com/thumb.jpg",
            "views": 1000000,
            "likes": 50000,
            "comments": 3000,
            "published_at": "2024-10-19T10:00:00Z"
        }

        result = analyze_success_factors(video)

        assert "title" in result
        assert "engagement" in result
        assert isinstance(result["title"], dict)
        assert isinstance(result["engagement"], dict)

    def test_engagement_metrics(self):
        """Test engagement metric calculation"""
        from agents.viral_video_agent.tools import analyze_success_factors

        video = {
            "video_id": "test123",
            "title": "Test Video",
            "views": 10000,
            "likes": 1000,  # 10% like ratio
            "comments": 500,
            "published_at": "2024-10-19T10:00:00Z"
        }

        result = analyze_success_factors(video)

        assert "engagement" in result
        engagement = result["engagement"]

        # Check like ratio calculation
        expected_like_ratio = 1000 / 10000
        assert abs(engagement["like_ratio"] - expected_like_ratio) < 0.01


# Pytest fixtures
@pytest.fixture
def sample_video_data():
    """Fixture providing sample video data"""
    return [
        {
            "platform": "youtube",
            "video_id": "abc123",
            "title": "신인 걸그룹 데뷔 무대",
            "channel": "MnetTV",
            "views": 3245820,
            "likes": 89234,
            "comments": 15234,
            "shares": 4521,
            "published_at": "2024-10-17T10:00:00Z",
            "url": "https://youtube.com/watch?v=abc123"
        },
        {
            "platform": "youtube",
            "video_id": "def456",
            "title": "커버댄스 챌린지",
            "channel": "DanceChannel",
            "views": 1500000,
            "likes": 45000,
            "comments": 8000,
            "shares": 2000,
            "published_at": "2024-10-18T15:00:00Z",
            "url": "https://youtube.com/watch?v=def456"
        }
    ]


def test_full_viral_pipeline(sample_video_data):
    """Test full viral analysis pipeline"""
    # 1. Detect spikes
    spike_result = detect_spike(sample_video_data, threshold=2.0)
    assert spike_result is not None

    # 2. Topic clustering
    texts = [item["title"] for item in sample_video_data]
    cluster_result = topic_cluster(texts, n_clusters=2)
    assert len(cluster_result["clusters"]) > 0

    # 3. Success factor analysis
    from agents.viral_video_agent.tools import analyze_success_factors
    factors = analyze_success_factors(sample_video_data[0])
    assert factors is not None


class TestZScoreCalculation:
    """Tests for z-score calculation"""

    def test_z_score_zero_for_mean(self):
        """Test z-score is 0 for mean value"""
        values = [10, 20, 30, 40, 50]
        mean_value = 30

        z_score = _calculate_z_score(mean_value, values)

        assert abs(z_score) < 0.1  # Should be close to 0

    def test_z_score_high_for_outlier(self):
        """Test z-score is high for outlier"""
        values = [10, 10, 10, 10, 100]
        outlier = 100

        z_score = _calculate_z_score(outlier, values)

        assert z_score > 2.0  # Clear outlier

    def test_z_score_with_zero_std(self):
        """Test z-score with zero standard deviation"""
        values = [10, 10, 10, 10, 10]  # All same values

        z_score = _calculate_z_score(10, values)

        assert z_score == 0.0  # Should handle gracefully

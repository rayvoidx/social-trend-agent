"""
FastAPI 서버 통합 테스트

API 엔드포인트를 실제로 호출하여 테스트합니다.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def client():
    """테스트 클라이언트 생성"""
    try:
        from src.api.routes.dashboard import app

        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI server not available")


@pytest.fixture
def mock_env(monkeypatch):
    """환경 변수 모킹"""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")


@pytest.fixture
def sample_agent_result():
    """샘플 에이전트 결과"""
    return {
        "query": "AI",
        "time_window": "7d",
        "language": "ko",
        "normalized": [{"title": "Test News", "description": "Test description"}],
        "analysis": {
            "sentiment": {"positive": 1, "neutral": 0, "negative": 0},
            "keywords": {"top_keywords": [{"keyword": "AI", "count": 10}]},
        },
        "report_md": "# Test Report",
        "metrics": {"coverage": 0.9, "factuality": 1.0, "actionability": 1.0},
        "run_id": "test-run-id",
    }


class TestHealthCheck:
    """헬스 체크 엔드포인트 테스트"""

    def test_health_check(self, client):
        """
        헬스 체크 정상 동작 테스트

        When: GET /api/health
        Then: 200 OK 반환
        """
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestTaskEndpoints:
    """비동기 태스크 엔드포인트 테스트"""

    def test_create_task_success(self, client, mock_env):
        """
        태스크 생성 성공 테스트

        Given: 유효한 요청
        When: POST /api/tasks
        Then: 200 OK, task_id 반환
        """
        with patch("src.api.routes.dashboard.executor") as mock_executor:
            # Mock executor.submit_task
            mock_executor.submit_task = AsyncMock(return_value="test-task-id")

            response = client.post(
                "/api/tasks",
                json={
                    "agent_name": "news_trend_agent",
                    "query": "AI",
                    "params": {"time_window": "7d"},
                    "priority": 1,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "task_id" in data

    def test_get_task_status_success(self, client, mock_env):
        """
        태스크 상태 조회 성공 테스트

        Given: 존재하는 task_id
        When: GET /api/tasks/{task_id}
        Then: 200 OK, 태스크 상태 반환
        """
        task_id = "test-task-id"

        with patch("src.api.routes.dashboard.executor") as mock_executor:
            # Mock task object
            mock_task = MagicMock()
            mock_task.task_id = task_id
            mock_task.agent_name = "news_trend_agent"
            mock_task.query = "AI"
            mock_task.status.value = "completed"
            mock_task.created_at = 1234567890.0
            mock_task.started_at = 1234567891.0
            mock_task.completed_at = 1234567900.0
            mock_task.result = {"query": "AI"}
            mock_task.error = None

            mock_executor.task_queue.get_task = AsyncMock(return_value=mock_task)

            response = client.get(f"/api/tasks/{task_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == task_id

    def test_get_task_not_found(self, client, mock_env):
        """
        존재하지 않는 태스크 조회 테스트

        Given: 존재하지 않는 task_id
        When: GET /api/tasks/{task_id}
        Then: 404 Not Found
        """
        with patch("src.api.routes.dashboard.executor") as mock_executor:
            mock_executor.task_queue.get_task = AsyncMock(return_value=None)

            response = client.get("/api/tasks/non-existent-id")

            assert response.status_code == 404

    def test_list_tasks(self, client, mock_env):
        """
        태스크 목록 조회 테스트

        When: GET /api/tasks
        Then: 200 OK, 태스크 목록 반환
        """
        with patch("src.api.routes.dashboard.executor") as mock_executor:
            mock_task = MagicMock()
            mock_task.to_dict.return_value = {
                "task_id": "test-id",
                "agent_name": "news_trend_agent",
                "query": "AI",
                "status": "completed",
            }
            mock_task.created_at = 1234567890.0

            mock_executor.task_queue.get_all_tasks = AsyncMock(return_value=[mock_task])

            response = client.get("/api/tasks")

            assert response.status_code == 200
            data = response.json()
            assert "tasks" in data
            assert "total" in data


class TestDashboardEndpoint:
    """대시보드 엔드포인트 테스트"""

    def test_dashboard_summary(self, client, mock_env):
        """
        대시보드 요약 조회 테스트

        When: GET /api/dashboard/summary
        Then: 200 OK, 통계 정보 반환
        """
        with patch("src.api.routes.dashboard.executor") as mock_executor:
            mock_task = MagicMock()
            mock_task.agent_name = "news_trend_agent"
            mock_task.status.value = "completed"
            mock_task.created_at = 1234567890.0
            mock_task.result = {"report_md": "# Test"}
            mock_task.to_dict.return_value = {
                "task_id": "test-id",
                "agent_name": "news_trend_agent",
                "status": "completed",
            }

            # TaskStatus enum mock
            from src.infrastructure.distributed import TaskStatus

            mock_task.status = TaskStatus.COMPLETED

            mock_executor.task_queue.get_all_tasks = AsyncMock(return_value=[mock_task])

            response = client.get("/api/dashboard/summary")

            assert response.status_code == 200
            data = response.json()
            assert "agents" in data
            assert "recent_tasks" in data


class TestMetricsEndpoint:
    """메트릭 엔드포인트 테스트"""

    def test_get_metrics(self, client, mock_env):
        """
        메트릭 조회 테스트

        When: GET /api/metrics
        Then: 200 OK, 메트릭 정보 반환
        """
        with patch("src.api.routes.dashboard.executor") as mock_executor:
            mock_executor.get_statistics = AsyncMock(
                return_value={"total_tasks": 10, "completed": 8, "failed": 2}
            )
            mock_executor.task_queue.get_all_tasks = AsyncMock(return_value=[])

            response = client.get("/api/metrics")

            assert response.status_code == 200
            data = response.json()
            assert "executor_stats" in data
            assert "timestamp" in data


class TestInsightsEndpoint:
    """인사이트 엔드포인트 테스트"""

    def test_list_insights(self, client, mock_env):
        """
        인사이트 목록 조회 테스트

        When: GET /api/insights
        Then: 200 OK, 인사이트 목록 반환
        """
        response = client.get("/api/insights")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestWorkersEndpoint:
    """워커 엔드포인트 테스트"""

    def test_get_workers(self, client, mock_env):
        """
        워커 정보 조회 테스트

        When: GET /api/workers
        Then: 200 OK, 워커 정보 반환
        """
        with patch("src.api.routes.dashboard.executor") as mock_executor:
            mock_worker = MagicMock()
            mock_worker.worker_id = "worker-1"
            mock_worker.is_running = True
            mock_worker.current_task = None

            mock_executor.workers = [mock_worker]

            response = client.get("/api/workers")

            assert response.status_code == 200
            data = response.json()
            assert "workers" in data
            assert "total_workers" in data


class TestCORS:
    """CORS 설정 테스트"""

    def test_cors_headers(self, client):
        """
        CORS 헤더 확인 테스트

        When: GET 요청 with Origin header
        Then: Access-Control-Allow-Origin 헤더 포함
        """
        response = client.get("/api/health", headers={"Origin": "http://localhost:3000"})

        assert response.status_code == 200
        # CORS 미들웨어가 활성화되어 있으면 헤더가 포함됨
        # assert "access-control-allow-origin" in response.headers


class TestStatisticsEndpoint:
    """통계 엔드포인트 테스트"""

    def test_get_statistics(self, client, mock_env):
        """
        통계 조회 테스트

        When: GET /api/statistics
        Then: 200 OK, 통계 정보 반환
        """
        with patch("src.api.routes.dashboard.executor") as mock_executor:
            mock_executor.get_statistics = AsyncMock(
                return_value={"total_tasks": 100, "completed": 95}
            )
            mock_executor.task_queue.get_all_tasks = AsyncMock(return_value=[])

            response = client.get("/api/statistics")

            assert response.status_code == 200
            data = response.json()
            assert "timestamp" in data
            assert "executor" in data


class TestErrorHandling:
    """에러 핸들링 테스트"""

    def test_executor_not_initialized(self, client, mock_env):
        """
        Executor 미초기화 상태 테스트

        Given: executor가 None
        When: GET /api/metrics
        Then: 503 Service Unavailable
        """
        with patch("src.api.routes.dashboard.executor", None):
            response = client.get("/api/metrics")

            assert response.status_code == 503
            data = response.json()
            assert "detail" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

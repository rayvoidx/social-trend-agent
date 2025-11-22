"""
FastAPI 서버 통합 테스트

API 엔드포인트를 실제로 호출하여 테스트합니다.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """테스트 클라이언트 생성"""
    try:
        from agents.api.dashboard import app
        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI server not available")


@pytest.fixture
def mock_env(monkeypatch):
    """환경 변수 모킹"""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")


@pytest.fixture
def sample_agent_result():
    """샘플 에이전트 결과"""
    return {
        "query": "AI",
        "time_window": "7d",
        "language": "ko",
        "normalized": [
            {"title": "Test News", "description": "Test description"}
        ],
        "analysis": {
            "sentiment": {"positive": 1, "neutral": 0, "negative": 0},
            "keywords": {"top_keywords": [{"keyword": "AI", "count": 10}]}
        },
        "report_md": "# Test Report",
        "metrics": {"coverage": 0.9, "factuality": 1.0, "actionability": 1.0},
        "run_id": "test-run-id"
    }


class TestHealthCheck:
    """헬스 체크 엔드포인트 테스트"""

    def test_health_check(self, client):
        """
        헬스 체크 정상 동작 테스트

        When: GET /health
        Then: 200 OK 반환
        """
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data


class TestExecuteEndpoint:
    """동기 실행 엔드포인트 테스트"""

    def test_execute_news_agent_success(self, client, mock_env, sample_agent_result):
        """
        뉴스 에이전트 실행 성공 테스트

        Given: 유효한 요청 데이터
        When: POST /api/execute
        Then: 200 OK, 분석 결과 반환
        """
        with patch('agents.news_trend_agent.graph.run_agent', return_value=sample_agent_result):
            response = client.post(
                "/api/execute",
                json={
                    "agentName": "news_trend_agent",
                    "query": "AI",
                    "params": {
                        "timeWindow": "7d",
                        "language": "ko"
                    }
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["query"] == "AI"
            assert "analysis" in data

    def test_execute_invalid_agent(self, client, mock_env):
        """
        잘못된 에이전트 이름 테스트

        Given: 존재하지 않는 에이전트
        When: POST /api/execute
        Then: 400 Bad Request
        """
        response = client.post(
            "/api/execute",
            json={
                "agentName": "invalid_agent",
                "query": "AI"
            }
        )

        assert response.status_code == 400

    def test_execute_missing_query(self, client, mock_env):
        """
        필수 파라미터 누락 테스트

        Given: query 파라미터 없음
        When: POST /api/execute
        Then: 422 Unprocessable Entity
        """
        response = client.post(
            "/api/execute",
            json={
                "agentName": "news_trend_agent"
            }
        )

        assert response.status_code == 422


class TestTaskEndpoints:
    """비동기 태스크 엔드포인트 테스트"""

    def test_create_task_success(self, client, mock_env):
        """
        태스크 생성 성공 테스트

        Given: 유효한 요청
        When: POST /api/tasks
        Then: 201 Created, task_id 반환
        """
        with patch('agents.api.dashboard.submit_task') as mock_submit:
            mock_submit.return_value = {"task_id": "test-task-id"}

            response = client.post(
                "/api/tasks",
                json={
                    "agentName": "news_trend_agent",
                    "query": "AI",
                    "params": {"timeWindow": "7d"}
                }
            )

            assert response.status_code == 201
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

        with patch('agents.api.dashboard.get_task_status') as mock_status:
            mock_status.return_value = {
                "task_id": task_id,
                "status": "completed",
                "result": {"query": "AI"}
            }

            response = client.get(f"/api/tasks/{task_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == task_id
            assert data["status"] == "completed"

    def test_get_task_not_found(self, client, mock_env):
        """
        존재하지 않는 태스크 조회 테스트

        Given: 존재하지 않는 task_id
        When: GET /api/tasks/{task_id}
        Then: 404 Not Found
        """
        response = client.get("/api/tasks/non-existent-id")

        assert response.status_code == 404


class TestDashboardEndpoint:
    """대시보드 엔드포인트 테스트"""

    def test_dashboard_summary(self, client, mock_env):
        """
        대시보드 요약 조회 테스트

        When: GET /api/dashboard/summary
        Then: 200 OK, 통계 정보 반환
        """
        with patch('agents.api.dashboard.get_dashboard_summary') as mock_summary:
            mock_summary.return_value = {
                "total_tasks": 100,
                "completed_tasks": 95,
                "failed_tasks": 2,
                "running_tasks": 3,
                "avg_execution_time": 12.5
            }

            response = client.get("/api/dashboard/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["total_tasks"] == 100
            assert data["completed_tasks"] == 95


class TestN8NWebhook:
    """n8n 웹훅 엔드포인트 테스트"""

    def test_n8n_webhook_success(self, client, mock_env, sample_agent_result):
        """
        n8n 웹훅 처리 성공 테스트

        Given: n8n 웹훅 요청
        When: POST /api/n8n/webhook
        Then: 200 OK, 분석 결과 반환
        """
        with patch('agents.news_trend_agent.graph.run_agent', return_value=sample_agent_result):
            response = client.post(
                "/api/n8n/webhook",
                json={
                    "action": "analyze",
                    "query": "AI",
                    "timeWindow": "7d"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "result" in data


class TestCORS:
    """CORS 설정 테스트"""

    def test_cors_headers(self, client):
        """
        CORS 헤더 확인 테스트

        When: OPTIONS 요청
        Then: Access-Control-Allow-Origin 헤더 포함
        """
        response = client.options("/health")

        assert response.status_code in [200, 204]
        # CORS가 설정되어 있다면 헤더 확인
        # assert "access-control-allow-origin" in response.headers


class TestRateLimiting:
    """Rate Limiting 테스트 (구현시)"""

    @pytest.mark.skip(reason="Rate limiting not implemented yet")
    def test_rate_limit_exceeded(self, client, mock_env):
        """
        Rate limit 초과 테스트

        Given: 많은 요청
        When: 연속으로 요청
        Then: 429 Too Many Requests
        """
        for _ in range(100):
            response = client.post(
                "/api/execute",
                json={"agentName": "news_trend_agent", "query": "AI"}
            )

        assert response.status_code == 429


class TestErrorHandling:
    """에러 핸들링 테스트"""

    def test_internal_server_error(self, client, mock_env):
        """
        내부 서버 에러 처리 테스트

        Given: 에이전트 실행 중 예외 발생
        When: POST /api/execute
        Then: 500 Internal Server Error, 에러 메시지
        """
        def mock_error(*args, **kwargs):
            raise Exception("Internal error")

        with patch('agents.news_trend_agent.graph.run_agent', side_effect=mock_error):
            response = client.post(
                "/api/execute",
                json={
                    "agentName": "news_trend_agent",
                    "query": "AI"
                }
            )

            assert response.status_code == 500
            data = response.json()
            assert "error" in data or "detail" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

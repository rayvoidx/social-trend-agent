"""
Integration tests for pipeline components.

Tests:
- LLM client integration
- Storage layer (Redis, PostgreSQL)
- RAG/Vector store
- Workflow management
- Monitoring middleware
"""
import os
import time
import uuid
import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# LLM Client Tests
# =============================================================================

class TestLLMClient:
    """Test LLM client integration."""

    def test_llm_client_initialization(self):
        """Test LLM client initializes with default provider."""
        from src.integrations.llm.llm_client import LLMClient

        client = LLMClient()
        assert client is not None
        assert client.provider in ["openai", "anthropic", "google", "groq", "azure", "ollama"]

    def test_llm_client_singleton(self):
        """Test get_llm_client returns singleton."""
        from src.integrations.llm.llm_client import get_llm_client

        client1 = get_llm_client()
        client2 = get_llm_client()
        assert client1 is client2

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set"
    )
    def test_openai_chat_completion(self):
        """Test OpenAI chat completion."""
        from src.integrations.llm.llm_client import LLMClient

        client = LLMClient(provider="openai", model="gpt-3.5-turbo")
        response = client.chat(
            messages=[
                {"role": "user", "content": "Say 'test' only"}
            ],
            max_tokens=10,
            temperature=0.0
        )

        assert response is not None
        assert len(response) > 0

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set"
    )
    def test_json_output(self):
        """Test LLM JSON output mode."""
        from src.integrations.llm.llm_client import LLMClient

        client = LLMClient(provider="openai", model="gpt-3.5-turbo")
        result = client.chat_json(
            messages=[
                {"role": "user", "content": "Return JSON: {\"status\": \"ok\"}"}
            ],
            temperature=0.0
        )

        assert isinstance(result, dict)
        assert "status" in result

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set"
    )
    def test_embedding_generation(self):
        """Test embedding generation."""
        from src.integrations.llm.llm_client import LLMClient

        client = LLMClient(provider="openai")
        embedding = client.get_embedding("Test text for embedding")

        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)


# =============================================================================
# Storage Tests
# =============================================================================

class TestRedisCache:
    """Test Redis cache integration."""

    def test_redis_cache_initialization(self):
        """Test Redis cache initializes with fallback."""
        from src.infrastructure.storage.redis_cache import RedisCache

        cache = RedisCache()
        assert cache is not None

    def test_cache_set_get(self):
        """Test cache set and get operations."""
        from src.infrastructure.storage.redis_cache import RedisCache

        cache = RedisCache(prefix="test")
        test_key = f"test_key_{uuid.uuid4().hex[:8]}"
        test_value = {"data": "test", "number": 42}

        # Set
        cache.set(test_key, test_value, ttl=60)

        # Get
        result = cache.get(test_key)
        assert result == test_value

        # Delete
        cache.delete(test_key)
        assert cache.get(test_key) is None

    def test_cache_deduplication(self):
        """Test cache deduplication functionality."""
        from src.infrastructure.storage.redis_cache import RedisCache

        cache = RedisCache(prefix="test")
        test_id = f"dedup_test_{uuid.uuid4().hex[:8]}"

        # First check - not duplicate
        is_dup = cache.check_duplicate(test_id)
        assert not is_dup

        # Second check - should be duplicate
        is_dup = cache.check_duplicate(test_id)
        assert is_dup

    def test_cache_job_state(self):
        """Test job state management."""
        from src.infrastructure.storage.redis_cache import RedisCache

        cache = RedisCache(prefix="test")
        job_id = f"job_{uuid.uuid4().hex[:8]}"

        # Set state
        cache.set_job_state(job_id, "running", {"started_at": time.time()})

        # Get state
        state = cache.get_job_state(job_id)
        assert state is not None
        assert state["status"] == "running"
        assert "started_at" in state

    def test_cache_counter(self):
        """Test counter operations."""
        from src.infrastructure.storage.redis_cache import RedisCache

        cache = RedisCache(prefix="test")
        counter_key = f"counter_{uuid.uuid4().hex[:8]}"

        # Increment
        val = cache.incr(counter_key)
        assert val == 1

        val = cache.incr(counter_key, 5)
        assert val == 6

        val = cache.decr(counter_key, 2)
        assert val == 4


class TestPostgresRepository:
    """Test PostgreSQL repository integration."""

    def test_repository_initialization(self):
        """Test repository initialization with fallback."""
        from src.infrastructure.storage.postgres_repository import InsightRepository

        repo = InsightRepository()
        assert repo is not None

    def test_insight_crud_operations(self):
        """Test insight CRUD operations."""
        from src.infrastructure.storage.postgres_repository import InsightRepository

        repo = InsightRepository()
        insight_id = f"insight_{uuid.uuid4().hex[:8]}"

        # Create
        insight_data = {
            "id": insight_id,
            "run_id": "test-run",
            "query": "test query",
            "title": "Test Insight",
            "description": "Test description",
            "impact": "high",
            "status": "draft"
        }

        created = repo.save(insight_data)
        assert created is not None
        assert created.get("id") == insight_id

        # Read
        retrieved = repo.find_by_id(insight_id)
        assert retrieved is not None
        assert retrieved.get("title") == "Test Insight"

        # Update
        updated = repo.update(insight_id, {"status": "approved"})
        assert updated is not None
        assert updated.get("status") == "approved"

        # List
        items = repo.find_all(limit=10)
        assert isinstance(items, list)

        # Delete
        deleted = repo.delete(insight_id)
        assert deleted is True

    def test_mission_repository(self):
        """Test mission repository operations."""
        from src.infrastructure.storage.postgres_repository import MissionRepository

        repo = MissionRepository()
        mission_id = f"mission_{uuid.uuid4().hex[:8]}"

        # Create
        mission_data = {
            "id": mission_id,
            "insight_id": "test-insight",
            "title": "Test Mission",
            "objective": "Test objective",
            "status": "draft"
        }

        created = repo.save(mission_data)
        assert created is not None

        # Read
        retrieved = repo.find_by_id(mission_id)
        assert retrieved is not None
        assert retrieved.get("title") == "Test Mission"

        # Cleanup
        repo.delete(mission_id)

    def test_creator_repository(self):
        """Test creator repository operations."""
        from src.infrastructure.storage.postgres_repository import CreatorRepository

        repo = CreatorRepository()
        creator_id = f"creator_{uuid.uuid4().hex[:8]}"

        # Create
        creator_data = {
            "id": creator_id,
            "platform": "instagram",
            "username": "test_creator",
            "follower_count": 10000,
            "engagement_rate": 0.05
        }

        created = repo.save(creator_data)
        assert created is not None

        # Read
        retrieved = repo.find_by_id(creator_id)
        assert retrieved is not None
        assert retrieved.get("platform") == "instagram"

        # Cleanup
        repo.delete(creator_id)


# =============================================================================
# RAG/Vector Store Tests
# =============================================================================

class TestPineconeStore:
    """Test Pinecone vector store integration."""

    def test_pinecone_store_initialization(self):
        """Test Pinecone store initializes with fallback."""
        from src.integrations.retrieval.pinecone_store import PineconeStore

        store = PineconeStore()
        assert store is not None

    @pytest.mark.skipif(
        not os.getenv("PINECONE_API_KEY"),
        reason="PINECONE_API_KEY not set"
    )
    def test_vector_upsert_and_query(self):
        """Test vector upsert and query operations."""
        from src.integrations.retrieval.pinecone_store import PineconeStore, get_pinecone_store
        from src.integrations.llm.llm_client import get_llm_client

        store = get_pinecone_store()
        client = get_llm_client()
        namespace = f"test_{uuid.uuid4().hex[:8]}"

        # Create test vectors
        test_items = [
            {"id": "item1", "text": "AI trends in 2024", "metadata": {"source": "test"}},
            {"id": "item2", "text": "Machine learning advances", "metadata": {"source": "test"}},
            {"id": "item3", "text": "Natural language processing", "metadata": {"source": "test"}},
        ]

        # Generate embeddings and upsert
        vectors = []
        for item in test_items:
            embedding = client.get_embedding(item["text"])
            vectors.append({
                "id": item["id"],
                "values": embedding,
                "metadata": {**item["metadata"], "text": item["text"]}
            })

        store.upsert(vectors, namespace=namespace)
        time.sleep(1)  # Wait for indexing

        # Query
        query_embedding = client.get_embedding("AI machine learning")
        results = store.query(
            query_embedding,
            top_k=2,
            namespace=namespace,
            include_metadata=True
        )

        assert "matches" in results
        assert len(results["matches"]) <= 2

        # Cleanup
        from src.integrations.retrieval.pinecone_store import clear_namespace
        clear_namespace(namespace)

    def test_build_corpus(self):
        """Test corpus building from items."""
        from src.integrations.retrieval.pinecone_store import build_corpus

        items = [
            {"title": "Test Item 1", "content": "Content 1", "source": "test"},
            {"title": "Test Item 2", "content": "Content 2", "source": "test"},
        ]

        corpus = build_corpus(items)

        assert isinstance(corpus, list)
        assert len(corpus) == len(items)
        for doc in corpus:
            assert "id" in doc
            assert "text" in doc
            assert "metadata" in doc


# =============================================================================
# Workflow Tests
# =============================================================================

class TestWorkflow:
    """Test workflow management."""

    def test_workflow_manager_singleton(self):
        """Test workflow manager singleton."""
        from src.core.workflow import get_workflow_manager

        manager1 = get_workflow_manager()
        manager2 = get_workflow_manager()
        assert manager1 is manager2

    def test_workflow_item_lifecycle(self):
        """Test complete workflow item lifecycle."""
        from src.core.workflow import (
            get_workflow_manager,
            WorkflowStatus,
            ReviewAction
        )

        manager = get_workflow_manager()
        item_id = f"workflow_{uuid.uuid4().hex[:8]}"

        # Create
        item = manager.create_item(
            id=item_id,
            type="insight",
            data={"title": "Test Insight"},
            created_by="test_user"
        )

        assert item.id == item_id
        assert item.status == WorkflowStatus.DRAFT

        # Submit for review
        success = manager.submit_for_review(item_id, assignee="reviewer")
        assert success
        assert item.status == WorkflowStatus.PENDING_REVIEW

        # Start review
        success = manager.start_review(item_id, "reviewer")
        assert success
        assert item.status == WorkflowStatus.IN_REVIEW

        # Submit review (approve)
        success = manager.submit_review(
            item_id,
            ReviewAction.APPROVE,
            "Looks good",
            "reviewer"
        )
        assert success
        assert item.status == WorkflowStatus.APPROVED

        # Publish
        success = manager.publish(item_id)
        assert success
        assert item.status == WorkflowStatus.PUBLISHED

        # Archive
        success = manager.archive(item_id, "Completed")
        assert success
        assert item.status == WorkflowStatus.ARCHIVED

    def test_workflow_rejection(self):
        """Test workflow rejection flow."""
        from src.core.workflow import (
            get_workflow_manager,
            WorkflowStatus,
            ReviewAction
        )

        manager = get_workflow_manager()
        item_id = f"reject_{uuid.uuid4().hex[:8]}"

        # Create and submit
        manager.create_item(id=item_id, type="insight", data={}, auto_submit=True)

        # Start and reject
        manager.start_review(item_id, "reviewer")
        success = manager.submit_review(
            item_id,
            ReviewAction.REJECT,
            "Needs more work",
            "reviewer"
        )

        assert success
        item = manager.get_item(item_id)
        assert item.status == WorkflowStatus.REJECTED

    def test_workflow_revision_request(self):
        """Test workflow revision request flow."""
        from src.core.workflow import (
            get_workflow_manager,
            WorkflowStatus,
            ReviewAction
        )

        manager = get_workflow_manager()
        item_id = f"revision_{uuid.uuid4().hex[:8]}"

        # Create and submit
        manager.create_item(id=item_id, type="insight", data={}, auto_submit=True)

        # Start and request revision
        manager.start_review(item_id, "reviewer")
        success = manager.submit_review(
            item_id,
            ReviewAction.REQUEST_REVISION,
            "Please add more details",
            "reviewer"
        )

        assert success
        item = manager.get_item(item_id)
        assert item.status == WorkflowStatus.REVISION_REQUESTED

        # Can go back to draft
        success = manager.transition_status(item_id, WorkflowStatus.DRAFT)
        assert success

    def test_invalid_transition(self):
        """Test invalid workflow transition fails."""
        from src.core.workflow import get_workflow_manager, WorkflowStatus

        manager = get_workflow_manager()
        item_id = f"invalid_{uuid.uuid4().hex[:8]}"

        # Create in draft
        manager.create_item(id=item_id, type="insight", data={})

        # Try invalid transition (draft -> published)
        success = manager.transition_status(item_id, WorkflowStatus.PUBLISHED)
        assert not success

        # Status should remain draft
        item = manager.get_item(item_id)
        assert item.status == WorkflowStatus.DRAFT

    def test_workflow_query_methods(self):
        """Test workflow query methods."""
        from src.core.workflow import get_workflow_manager, WorkflowStatus

        manager = get_workflow_manager()

        # Create test items
        for i in range(3):
            item_id = f"query_test_{i}_{uuid.uuid4().hex[:4]}"
            manager.create_item(
                id=item_id,
                type="insight",
                data={},
                auto_submit=True
            )

        # Query pending reviews
        pending = manager.get_pending_reviews()
        assert isinstance(pending, list)
        assert len(pending) >= 3

        # Query by status
        items = manager.list_items(status=WorkflowStatus.PENDING_REVIEW)
        assert isinstance(items, list)


# =============================================================================
# Monitoring Tests
# =============================================================================

class TestMonitoring:
    """Test monitoring and metrics."""

    def test_metrics_registry_singleton(self):
        """Test metrics registry singleton."""
        from src.infrastructure.monitoring import get_metrics_registry

        registry1 = get_metrics_registry()
        registry2 = get_metrics_registry()
        assert registry1 is registry2

    def test_record_llm_request(self):
        """Test recording LLM request metrics."""
        from src.infrastructure.monitoring import record_llm_request

        # Should not raise
        record_llm_request(
            provider="openai",
            model="gpt-4",
            duration_seconds=1.5,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
            success=True
        )

    def test_record_api_request(self):
        """Test recording API request metrics."""
        from src.infrastructure.monitoring import record_api_request

        # Should not raise
        record_api_request(
            service="test",
            endpoint="/test",
            duration_seconds=0.5,
            success=True
        )

    def test_rate_limiter(self):
        """Test rate limiter functionality."""
        from src.infrastructure.monitoring.middleware import RateLimiter, RateLimitConfig

        config = RateLimitConfig(
            requests_per_minute=5,
            requests_per_hour=10
        )
        limiter = RateLimiter(config)

        # First 5 requests should be allowed
        for i in range(5):
            allowed, info = limiter.is_allowed("test_client")
            assert allowed, f"Request {i+1} should be allowed"

        # 6th request should be rate limited
        allowed, info = limiter.is_allowed("test_client")
        assert not allowed
        assert info.get("limit") == "minute"

    def test_get_metrics_export(self):
        """Test Prometheus metrics export."""
        from src.infrastructure.monitoring import get_metrics, PROMETHEUS_AVAILABLE

        metrics_bytes = get_metrics()

        if PROMETHEUS_AVAILABLE:
            assert isinstance(metrics_bytes, bytes)
        else:
            assert metrics_bytes == b""


# =============================================================================
# Structured Output Tests
# =============================================================================

class TestStructuredOutput:
    """Test structured output schemas and Self-Refine."""

    def test_sentiment_analysis_schema(self):
        """Test sentiment analysis schema validation."""
        from src.integrations.llm.structured_output import SentimentAnalysis, SentimentType

        data = {
            "overall": "positive",
            "positive_pct": 60.5,
            "neutral_pct": 30.0,
            "negative_pct": 9.5,
            "confidence": 0.85,
            "key_emotions": ["happy", "excited"],
            "sentiment_drivers": [],
            "summary": "Overall positive sentiment"
        }

        result = SentimentAnalysis(**data)
        assert result.overall == SentimentType.POSITIVE
        assert result.positive_pct == 60.5

    def test_insight_generation_schema(self):
        """Test insight generation schema validation."""
        from src.integrations.llm.structured_output import (
            InsightGeneration,
            Insight,
            Recommendation,
            ImpactLevel,
            Priority,
            Timeline
        )

        data = {
            "summary": "Test summary",
            "key_findings": ["Finding 1", "Finding 2"],
            "insights": [
                {
                    "title": "Insight 1",
                    "description": "Description",
                    "evidence": "Evidence",
                    "impact": "high"
                }
            ],
            "recommendations": [
                {
                    "action": "Action 1",
                    "rationale": "Rationale",
                    "priority": "high",
                    "timeline": "immediate"
                }
            ],
            "risks": ["Risk 1"],
            "opportunities": ["Opportunity 1"]
        }

        result = InsightGeneration(**data)
        assert len(result.insights) == 1
        assert result.insights[0].impact == ImpactLevel.HIGH
        assert result.recommendations[0].priority == Priority.HIGH

    def test_quality_score(self):
        """Test quality score calculation."""
        from src.integrations.llm.structured_output import QualityScore

        score = QualityScore(
            specificity=8,
            actionability=7,
            evidence_based=9,
            clarity=8,
            completeness=8
        )

        assert score.total == 8.0  # (8+7+9+8+8)/5


# =============================================================================
# Analysis Tools Tests
# =============================================================================

class TestAnalysisTools:
    """Test LLM-based analysis tools."""

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set"
    )
    def test_sentiment_analysis(self):
        """Test sentiment analysis function."""
        from src.integrations.llm.analysis_tools import analyze_sentiment_llm

        texts = [
            "Great product! I love it.",
            "Terrible service, very disappointed.",
            "It's okay, nothing special."
        ]

        result = analyze_sentiment_llm(texts)

        assert "overall" in result
        assert "positive_pct" in result
        assert "summary" in result

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set"
    )
    def test_keyword_extraction(self):
        """Test keyword extraction function."""
        from src.integrations.llm.analysis_tools import extract_keywords_llm

        texts = [
            "AI and machine learning are transforming industries",
            "Natural language processing enables chatbots",
            "Deep learning models improve accuracy"
        ]

        result = extract_keywords_llm(texts)

        assert "top_keywords" in result
        assert isinstance(result["top_keywords"], list)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing without API calls."""
    with patch("src.integrations.llm.llm_client.get_llm_client") as mock:
        client = MagicMock()
        client.chat.return_value = "Test response"
        client.chat_json.return_value = {"status": "ok"}
        client.get_embedding.return_value = [0.1] * 1536
        mock.return_value = client
        yield client


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

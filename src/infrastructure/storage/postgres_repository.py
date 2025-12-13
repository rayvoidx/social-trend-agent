"""
PostgreSQL 영속 저장소

기능:
- Insight, Mission, Creator, Reward 저장
- 트랜잭션 관리
- 커넥션 풀링
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# SQLAlchemy (lazy import)
_engine = None
_SessionLocal = None

T = TypeVar("T")


def get_postgres_engine():
    """Get SQLAlchemy engine (singleton)."""
    global _engine, _SessionLocal

    if _engine is not None:
        return _engine

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        database_url = os.getenv("DATABASE_URL", "postgresql://localhost:5432/trend_analysis")

        pool_size = int(os.getenv("POSTGRES_POOL_SIZE", "20"))
        max_overflow = int(os.getenv("POSTGRES_MAX_OVERFLOW", "10"))

        _engine = create_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            echo=os.getenv("DEBUG", "false").lower() == "true",
        )

        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

        logger.info(f"Connected to PostgreSQL: {database_url.split('@')[-1]}")
        return _engine

    except ImportError:
        logger.warning("SQLAlchemy not installed. Using in-memory fallback.")
        return None
    except Exception as e:
        logger.warning(f"Failed to connect to PostgreSQL: {e}")
        return None


def get_session():
    """Get database session."""
    global _SessionLocal
    if _SessionLocal is None:
        get_postgres_engine()
    if _SessionLocal:
        return _SessionLocal()
    return None


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = get_session()
    if session is None:
        yield None
        return

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# =============================================================================
# SQLAlchemy Models
# =============================================================================


def create_tables():
    """Create database tables."""
    engine = get_postgres_engine()
    if engine is None:
        return

    try:
        from sqlalchemy import (
            Column,
            String,
            Float,
            Integer,
            DateTime,
            Text,
            JSON,
            MetaData,
            Table,
            Index,
        )

        metadata = MetaData()

        # Insights table
        Table(
            "insights",
            metadata,
            Column("id", String(64), primary_key=True),
            Column("source", String(50), nullable=False),
            Column("query", String(500), nullable=False),
            Column("time_window", String(20)),
            Column("language", String(10)),
            Column("sentiment_summary", Text),
            Column("top_keywords", JSON),
            Column("analysis_data", JSON),
            Column("metrics", JSON),
            Column("report_md", Text),
            Column("run_id", String(64)),
            Column("report_path", String(500)),
            Column("status", String(20), default="draft"),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
            Index("ix_insights_source", "source"),
            Index("ix_insights_query", "query"),
            Index("ix_insights_created_at", "created_at"),
        )

        # Missions table
        Table(
            "missions",
            metadata,
            Column("id", String(64), primary_key=True),
            Column("insight_id", String(64)),
            Column("title", String(500), nullable=False),
            Column("objective", Text),
            Column("target_audience", String(500)),
            Column("content_guidelines", JSON),
            Column("kpis", JSON),
            Column("budget", Float),
            Column("deadline", DateTime),
            Column("status", String(20), default="draft"),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
            Index("ix_missions_insight_id", "insight_id"),
            Index("ix_missions_status", "status"),
        )

        # Creators table
        Table(
            "creators",
            metadata,
            Column("id", String(64), primary_key=True),
            Column("name", String(200), nullable=False),
            Column("platform", String(50)),
            Column("handle", String(200)),
            Column("followers", Integer, default=0),
            Column("engagement_rate", Float, default=0.0),
            Column("categories", JSON),
            Column("contact_info", JSON),
            Column("past_collaborations", JSON),
            Column("rating", Float),
            Column("status", String(20), default="active"),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
            Index("ix_creators_platform", "platform"),
            Index("ix_creators_followers", "followers"),
        )

        # Collected items table (for raw data)
        Table(
            "collected_items",
            metadata,
            Column("id", String(64), primary_key=True),
            Column("run_id", String(64)),
            Column("source", String(50)),
            Column("title", String(500)),
            Column("url", String(1000)),
            Column("content", Text),
            Column("published_at", DateTime),
            Column("author", String(200)),
            Column("views", Integer, default=0),
            Column("likes", Integer, default=0),
            Column("comments", Integer, default=0),
            Column("shares", Integer, default=0),
            Column("content_hash", String(64)),
            Column("raw_data", JSON),
            Column("created_at", DateTime, default=datetime.utcnow),
            Index("ix_collected_items_run_id", "run_id"),
            Index("ix_collected_items_source", "source"),
            Index("ix_collected_items_content_hash", "content_hash"),
        )

        metadata.create_all(engine)
        logger.info("Database tables created successfully")

    except Exception as e:
        logger.error(f"Failed to create tables: {e}")


# =============================================================================
# Generic Repository
# =============================================================================


class PostgresRepository(Generic[T]):
    """
    Generic PostgreSQL repository.

    인메모리 폴백을 지원하는 영속 저장소.
    """

    def __init__(self, table_name: str):
        self.table_name = table_name
        self._engine = get_postgres_engine()

        # In-memory fallback
        self._memory_store: Dict[str, Dict[str, Any]] = {}

    def create(self, id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        새 레코드 생성 (save 메서드 내부 사용).
        """
        if self._engine:
            try:
                with session_scope() as session:
                    if session:
                        from sqlalchemy import text

                        columns = ", ".join(data.keys())
                        placeholders = ", ".join([f":{k}" for k in data.keys()])

                        sql = text(
                            f"""
                            INSERT INTO {self.table_name} (id, {columns})
                            VALUES (:id, {placeholders})
                            ON CONFLICT (id) DO UPDATE SET
                            {', '.join([f'{k} = :{k}' for k in data.keys()])}
                        """
                        )

                        session.execute(sql, {"id": id, **data})
                        logger.debug(f"Created {self.table_name} record: {id}")
                        return {"id": id, **data}

            except Exception as e:
                logger.error(f"PostgreSQL create error: {e}")

        # Fallback
        self._memory_store[id] = {"id": id, **data}
        return self._memory_store[id]

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        데이터 저장 (Upsert). id 필드가 필수입니다.
        """
        if "id" not in data:
            raise ValueError("Data must contain 'id' field")

        # Extract ID and pass rest as data (actually pass full data including ID to columns is fine if create handles it)
        # create method expects id separately but also data.
        # It constructs INSERT ... (id, ...) VALUES (:id, ...).
        # And data keys are used for columns. If 'id' is in data, it might duplicate column 'id'?
        # In create: columns = ", ".join(data.keys()).
        # If 'id' is in data, columns will have 'id'.
        # And INSERT INTO table (id, id, ...) -> Error.
        # So we must remove 'id' from data passed to create, OR update create.
        # Actually create method logic:
        # columns = ", ".join(data.keys())
        # INSERT INTO table (id, {columns})
        # So 'id' should NOT be in data keys if it's already first arg.

        id_val = data["id"]
        data_without_id = {k: v for k, v in data.items() if k != "id"}
        return self.create(id_val, data_without_id)

    def get(self, id: str) -> Optional[Dict[str, Any]]:
        """ID로 레코드 조회."""
        if self._engine:
            try:
                with session_scope() as session:
                    if session:
                        from sqlalchemy import text

                        sql = text(f"SELECT * FROM {self.table_name} WHERE id = :id")
                        result = session.execute(sql, {"id": id}).fetchone()
                        if result:
                            return dict(result._mapping)

            except Exception as e:
                logger.error(f"PostgreSQL get error: {e}")

        # Fallback
        return self._memory_store.get(id)

    def update(self, id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """레코드 업데이트."""
        if self._engine:
            try:
                with session_scope() as session:
                    if session:
                        from sqlalchemy import text

                        set_clause = ", ".join([f"{k} = :{k}" for k in data.keys()])

                        sql = text(
                            f"""
                            UPDATE {self.table_name}
                            SET {set_clause}, updated_at = NOW()
                            WHERE id = :id
                        """
                        )

                        session.execute(sql, {"id": id, **data})
                        return self.get(id)

            except Exception as e:
                logger.error(f"PostgreSQL update error: {e}")

        # Fallback
        if id in self._memory_store:
            self._memory_store[id].update(data)
            return self._memory_store[id]
        return None

    def delete(self, id: str) -> bool:
        """레코드 삭제."""
        if self._engine:
            try:
                with session_scope() as session:
                    if session:
                        from sqlalchemy import text

                        sql = text(f"DELETE FROM {self.table_name} WHERE id = :id")
                        session.execute(sql, {"id": id})
                        return True

            except Exception as e:
                logger.error(f"PostgreSQL delete error: {e}")

        # Fallback
        if id in self._memory_store:
            del self._memory_store[id]
            return True
        return False

    def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """레코드 목록 조회."""
        if self._engine:
            try:
                with session_scope() as session:
                    if session:
                        from sqlalchemy import text

                        where_clause = ""
                        params = {}

                        if filters:
                            conditions = []
                            for k, v in filters.items():
                                conditions.append(f"{k} = :{k}")
                                params[k] = v
                            where_clause = "WHERE " + " AND ".join(conditions)

                        direction = "DESC" if order_desc else "ASC"
                        sql = text(
                            f"""
                            SELECT * FROM {self.table_name}
                            {where_clause}
                            ORDER BY {order_by} {direction}
                            LIMIT :limit OFFSET :offset
                        """
                        )

                        params["limit"] = limit
                        params["offset"] = offset

                        results = session.execute(sql, params).fetchall()
                        return [dict(row._mapping) for row in results]

            except Exception as e:
                logger.error(f"PostgreSQL list error: {e}")

        # Fallback
        items = list(self._memory_store.values())
        if filters:
            items = [item for item in items if all(item.get(k) == v for k, v in filters.items())]
        items.sort(key=lambda x: x.get(order_by, ""), reverse=order_desc)
        return items[offset : offset + limit]

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """레코드 수 조회."""
        if self._engine:
            try:
                with session_scope() as session:
                    if session:
                        from sqlalchemy import text

                        where_clause = ""
                        params = {}

                        if filters:
                            conditions = []
                            for k, v in filters.items():
                                conditions.append(f"{k} = :{k}")
                                params[k] = v
                            where_clause = "WHERE " + " AND ".join(conditions)

                        sql = text(f"SELECT COUNT(*) FROM {self.table_name} {where_clause}")
                        result = session.execute(sql, params).scalar()
                        return result or 0

            except Exception as e:
                logger.error(f"PostgreSQL count error: {e}")

        # Fallback
        items = list(self._memory_store.values())
        if filters:
            items = [item for item in items if all(item.get(k) == v for k, v in filters.items())]
        return len(items)

    # Aliases for compatibility
    find_by_id = get
    find_all = list


# =============================================================================
# Specialized Repositories
# =============================================================================


class InsightRepository(PostgresRepository):
    """Insight 전용 저장소."""

    def __init__(self):
        super().__init__("insights")

    def get_by_source(self, source: str, limit: int = 50) -> List[Dict[str, Any]]:
        """소스별 인사이트 조회."""
        return self.list(filters={"source": source}, limit=limit)

    def get_recent(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """최근 인사이트 조회."""
        if self._engine:
            try:
                with session_scope() as session:
                    if session:
                        from sqlalchemy import text

                        sql = text(
                            f"""
                            SELECT * FROM {self.table_name}
                            WHERE created_at > NOW() - INTERVAL '{hours} hours'
                            ORDER BY created_at DESC
                            LIMIT :limit
                        """
                        )
                        results = session.execute(sql, {"limit": limit}).fetchall()
                        return [dict(row._mapping) for row in results]
            except Exception as e:
                logger.error(f"get_recent error: {e}")

        return self.list(limit=limit)

    def update_status(self, id: str, status: str) -> bool:
        """인사이트 상태 업데이트."""
        result = self.update(id, {"status": status})
        return result is not None


class MissionRepository(PostgresRepository):
    """Mission 전용 저장소."""

    def __init__(self):
        super().__init__("missions")

    def get_by_insight(self, insight_id: str) -> List[Dict[str, Any]]:
        """인사이트별 미션 조회."""
        return self.list(filters={"insight_id": insight_id})

    def get_pending_review(self, limit: int = 50) -> List[Dict[str, Any]]:
        """검토 대기 중인 미션 조회."""
        return self.list(filters={"status": "pending_review"}, limit=limit)


class CreatorRepository(PostgresRepository):
    """Creator 전용 저장소."""

    def __init__(self):
        super().__init__("creators")

    def get_by_platform(self, platform: str, limit: int = 50) -> List[Dict[str, Any]]:
        """플랫폼별 크리에이터 조회."""
        return self.list(filters={"platform": platform}, limit=limit)

    def get_top_creators(self, limit: int = 20, min_followers: int = 0) -> List[Dict[str, Any]]:
        """상위 크리에이터 조회."""
        if self._engine:
            try:
                with session_scope() as session:
                    if session:
                        from sqlalchemy import text

                        sql = text(
                            f"""
                            SELECT * FROM {self.table_name}
                            WHERE followers >= :min_followers
                            ORDER BY engagement_rate DESC, followers DESC
                            LIMIT :limit
                        """
                        )
                        results = session.execute(
                            sql, {"min_followers": min_followers, "limit": limit}
                        ).fetchall()
                        return [dict(row._mapping) for row in results]
            except Exception as e:
                logger.error(f"get_top_creators error: {e}")

        return self.list(order_by="followers", limit=limit)


class CollectedItemRepository(PostgresRepository):
    """수집 아이템 전용 저장소."""

    def __init__(self):
        super().__init__("collected_items")

    def get_by_run(self, run_id: str) -> List[Dict[str, Any]]:
        """실행별 수집 아이템 조회."""
        return self.list(filters={"run_id": run_id})

    def check_exists(self, content_hash: str) -> bool:
        """콘텐츠 해시로 존재 여부 확인."""
        items = self.list(filters={"content_hash": content_hash}, limit=1)
        return len(items) > 0


# =============================================================================
# Initialization
# =============================================================================


def init_database():
    """Initialize database (create tables if not exist)."""
    engine = get_postgres_engine()
    if engine:
        create_tables()
        logger.info("Database initialized")
    else:
        logger.warning("Using in-memory storage (PostgreSQL not available)")


# Global repository instances
_insight_repo: Optional[InsightRepository] = None
_mission_repo: Optional[MissionRepository] = None
_creator_repo: Optional[CreatorRepository] = None


def get_insight_repository() -> InsightRepository:
    """Get insight repository instance."""
    global _insight_repo
    if _insight_repo is None:
        _insight_repo = InsightRepository()
    return _insight_repo


def get_mission_repository() -> MissionRepository:
    """Get mission repository instance."""
    global _mission_repo
    if _mission_repo is None:
        _mission_repo = MissionRepository()
    return _mission_repo


def get_creator_repository() -> CreatorRepository:
    """Get creator repository instance."""
    global _creator_repo
    if _creator_repo is None:
        _creator_repo = CreatorRepository()
    return _creator_repo

"""
Persistent storage layer with Redis and PostgreSQL.
"""
from .redis_cache import RedisCache, get_redis_client, get_cache
from .postgres_repository import (
    PostgresRepository,
    get_postgres_engine,
    InsightRepository,
    MissionRepository,
    CreatorRepository,
    CollectedItemRepository,
    get_insight_repository,
    get_mission_repository,
    get_creator_repository,
)

# Aliases for compatibility
get_redis_cache = get_cache


def get_collected_item_repository():
    """Get collected item repository singleton."""
    return CollectedItemRepository()


__all__ = [
    "RedisCache",
    "get_redis_client",
    "get_redis_cache",
    "get_cache",
    "PostgresRepository",
    "get_postgres_engine",
    "InsightRepository",
    "MissionRepository",
    "CreatorRepository",
    "CollectedItemRepository",
    "get_insight_repository",
    "get_mission_repository",
    "get_creator_repository",
    "get_collected_item_repository",
]

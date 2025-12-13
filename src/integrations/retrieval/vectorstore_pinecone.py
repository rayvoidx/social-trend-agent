"""
Pinecone Vector Store implementation.

Environment Variables:
- PINECONE_API_KEY: Pinecone API key
- PINECONE_ENVIRONMENT: Pinecone environment (optional, for legacy)
"""

import os
import logging
from typing import List, Dict, Any, Optional
import hashlib

logger = logging.getLogger(__name__)


class PineconeVectorStore:
    """
    Pinecone vector store for semantic search.

    Handles:
    - Index creation and management
    - Vector upsert and query
    - Metadata filtering
    """

    def __init__(
        self,
        index_name: str,
        dimension: int = 3072,  # text-embedding-3-large dimension
        metric: str = "cosine",
        namespace: str = "",
    ):
        """
        Initialize Pinecone vector store.

        Args:
            index_name: Name of the Pinecone index
            dimension: Vector dimension (default 3072 for text-embedding-3-large)
            metric: Distance metric (cosine, euclidean, dotproduct)
            namespace: Optional namespace for multi-tenancy
        """
        from pinecone import Pinecone, ServerlessSpec

        self.api_key = os.getenv("PINECONE_API_KEY")
        if not self.api_key:
            raise ValueError("PINECONE_API_KEY environment variable is required")

        self.index_name = index_name
        self.dimension = dimension
        self.metric = metric
        self.namespace = namespace

        # Initialize Pinecone client
        self.pc = Pinecone(api_key=self.api_key)

        # Create index if it doesn't exist
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]

        if index_name not in existing_indexes:
            logger.info(f"Creating Pinecone index: {index_name}")
            self.pc.create_index(
                name=index_name,
                dimension=dimension,
                metric=metric,
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )

        self.index = self.pc.Index(index_name)
        logger.info(f"PineconeVectorStore initialized: index={index_name}, dimension={dimension}")

    def upsert(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """
        Upsert vectors into the index.

        Args:
            ids: List of vector IDs
            vectors: List of vectors
            metadatas: Optional list of metadata dicts

        Returns:
            Number of vectors upserted
        """
        if metadatas is None:
            metadatas = [{}] * len(ids)

        # Prepare vectors for upsert
        records = []
        for i, (id_, vec, meta) in enumerate(zip(ids, vectors, metadatas)):
            # Clean metadata (Pinecone doesn't support nested dicts)
            clean_meta = {}
            for k, v in meta.items():
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                elif isinstance(v, list) and all(isinstance(x, str) for x in v):
                    clean_meta[k] = v

            records.append({"id": id_, "values": vec, "metadata": clean_meta})

        # Upsert in batches
        batch_size = 100
        total_upserted = 0

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            self.index.upsert(vectors=batch, namespace=self.namespace)
            total_upserted += len(batch)

        logger.info(f"Upserted {total_upserted} vectors to {self.index_name}")
        return total_upserted

    def query(
        self,
        vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Query the index for similar vectors.

        Args:
            vector: Query vector
            top_k: Number of results to return
            filter: Optional metadata filter
            include_metadata: Whether to include metadata in results

        Returns:
            List of matches with id, score, and metadata
        """
        results = self.index.query(
            vector=vector,
            top_k=top_k,
            filter=filter,
            include_metadata=include_metadata,
            namespace=self.namespace,
        )

        matches = []
        for match in results.matches:
            matches.append(
                {
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata if include_metadata else {},
                }
            )

        return matches

    def delete(self, ids: Optional[List[str]] = None, delete_all: bool = False):
        """
        Delete vectors from the index.

        Args:
            ids: List of vector IDs to delete
            delete_all: If True, delete all vectors in namespace
        """
        if delete_all:
            self.index.delete(delete_all=True, namespace=self.namespace)
            logger.info(f"Deleted all vectors from {self.index_name}")
        elif ids:
            self.index.delete(ids=ids, namespace=self.namespace)
            logger.info(f"Deleted {len(ids)} vectors from {self.index_name}")

    def describe_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return self.index.describe_index_stats()


# Alias for backward compatibility
PineconeStore = PineconeVectorStore


def get_pinecone_store(
    index_name: str, dimension: int = 3072, namespace: str = ""
) -> PineconeVectorStore:
    """
    Get or create a Pinecone vector store.

    Args:
        index_name: Name of the Pinecone index
        dimension: Vector dimension
        namespace: Optional namespace

    Returns:
        PineconeVectorStore instance
    """
    return PineconeVectorStore(index_name=index_name, dimension=dimension, namespace=namespace)


def generate_vector_id(content: str, prefix: str = "") -> str:
    """
    Generate a unique ID for a vector based on content hash.

    Args:
        content: Content to hash
        prefix: Optional prefix for the ID

    Returns:
        Unique vector ID
    """
    hash_value = hashlib.md5(content.encode()).hexdigest()[:12]
    if prefix:
        return f"{prefix}_{hash_value}"
    return hash_value

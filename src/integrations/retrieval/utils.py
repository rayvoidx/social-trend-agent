"""
Retrieval utility functions.
"""

import logging
from typing import List, Dict, Any, Optional
import hashlib

logger = logging.getLogger(__name__)


def build_corpus(items: List[Dict[str, Any]], text_fields: List[str] = None) -> List[str]:
    """
    Build a corpus from items for embedding.

    Args:
        items: List of items with text fields
        text_fields: Fields to extract text from (default: title, description, content)

    Returns:
        List of text strings
    """
    if text_fields is None:
        text_fields = ["title", "description", "content", "text"]

    corpus = []
    for item in items:
        texts = []
        for field in text_fields:
            if field in item and item[field]:
                texts.append(str(item[field]))
        corpus.append(" ".join(texts))

    return corpus


def retrieve_relevant_items(
    query: str,
    items: List[Dict[str, Any]],
    top_k: int = 10,
    vector_store=None,
    llm_client=None
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant items using vector similarity search.

    If vector_store and llm_client are provided, uses semantic search.
    Otherwise falls back to keyword matching.

    Args:
        query: Search query
        items: List of items to search
        top_k: Number of results
        vector_store: Optional PineconeVectorStore instance
        llm_client: Optional LLMClient for embeddings

    Returns:
        List of relevant items
    """
    if not items:
        return []

    # If no vector store, use keyword matching
    if vector_store is None or llm_client is None:
        return _keyword_retrieve(query, items, top_k)

    try:
        # Build corpus and generate IDs
        corpus = build_corpus(items)
        ids = [hashlib.md5(text.encode()).hexdigest()[:12] for text in corpus]

        # Get embeddings
        vectors = llm_client.get_embeddings_batch(corpus)

        # Prepare metadata
        metadatas = []
        for i, item in enumerate(items):
            meta = {
                "index": i,
                "title": item.get("title", "")[:500],
                "source": item.get("source", "")
            }
            metadatas.append(meta)

        # Upsert to vector store
        vector_store.upsert(ids, vectors, metadatas)

        # Query
        query_vector = llm_client.get_embedding(query)
        matches = vector_store.query(query_vector, top_k=top_k)

        # Get original items
        results = []
        for match in matches:
            idx = match.get("metadata", {}).get("index")
            if idx is not None and idx < len(items):
                results.append(items[idx])

        return results if results else _keyword_retrieve(query, items, top_k)

    except Exception as e:
        logger.warning(f"Vector retrieval failed, falling back to keyword: {e}")
        return _keyword_retrieve(query, items, top_k)


def _keyword_retrieve(
    query: str,
    items: List[Dict[str, Any]],
    top_k: int
) -> List[Dict[str, Any]]:
    """
    Simple keyword-based retrieval as fallback.

    Args:
        query: Search query
        items: List of items
        top_k: Number of results

    Returns:
        List of relevant items
    """
    query_terms = set(query.lower().split())

    scored_items = []
    for item in items:
        # Build text from item
        text_parts = []
        for field in ["title", "description", "content", "text"]:
            if field in item and item[field]:
                text_parts.append(str(item[field]).lower())
        text = " ".join(text_parts)

        # Score by term overlap
        text_terms = set(text.split())
        overlap = len(query_terms & text_terms)
        score = overlap / max(len(query_terms), 1)

        scored_items.append((score, item))

    # Sort by score descending
    scored_items.sort(key=lambda x: x[0], reverse=True)

    return [item for score, item in scored_items[:top_k]]

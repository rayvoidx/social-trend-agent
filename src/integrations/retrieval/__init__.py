"""
Retrieval module for vector stores.

Supports:
- Pinecone: Managed vector database
"""

from .vectorstore_pinecone import PineconeVectorStore, PineconeStore, get_pinecone_store
from .utils import build_corpus, retrieve_relevant_items

__all__ = [
    "PineconeVectorStore",
    "PineconeStore",
    "get_pinecone_store",
    "build_corpus",
    "retrieve_relevant_items",
]

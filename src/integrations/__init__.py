"""
External service integrations.

Modules:
- llm: LLM providers (OpenAI, Anthropic, Google, Groq, etc.)
- retrieval: Vector stores (Pinecone, etc.)
- social: Social media APIs (to be implemented as MCP)
"""

from .llm import (
    get_llm_client,
    LLMClient,
    analyze_sentiment_llm,
    extract_keywords_llm,
    cluster_topics_llm,
    generate_insights_llm,
    AnalysisResult,
)
from .retrieval import (
    PineconeStore,
    PineconeVectorStore,
    get_pinecone_store,
    build_corpus,
    retrieve_relevant_items,
)

__all__ = [
    # LLM
    "get_llm_client",
    "LLMClient",
    "analyze_sentiment_llm",
    "extract_keywords_llm",
    "cluster_topics_llm",
    "generate_insights_llm",
    "AnalysisResult",
    # Retrieval
    "PineconeStore",
    "PineconeVectorStore",
    "get_pinecone_store",
    "build_corpus",
    "retrieve_relevant_items",
]

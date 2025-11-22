"""
LLM Client module supporting multiple providers.

Environment Variables:
- OPENAI_API_KEY: OpenAI API key
- ANTHROPIC_API_KEY: Anthropic API key
- GEMINI_API_KEY: Google Gemini API key
- VOYAGE_API_KEY: Voyage AI API key for embeddings
- GEMINI_MODEL_NAME: Gemini model name (default: gemini-1.5-pro)
- ANTHROPIC_MODEL_NAME: Anthropic model name (default: claude-3-5-sonnet-20241022)
- GEMINI_EMBEDDING_MODEL_NAME: Gemini embedding model (default: models/embedding-001)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text."""
        pass

    @abstractmethod
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts."""
        pass


class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI embedding provider."""

    def __init__(self, model_name: str = "text-embedding-3-large"):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model_name = model_name

    def get_embedding(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            input=text,
            model=self.model_name
        )
        return response.data[0].embedding

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(
            input=texts,
            model=self.model_name
        )
        return [item.embedding for item in response.data]


class VoyageEmbedding(EmbeddingProvider):
    """Voyage AI embedding provider for Anthropic."""

    def __init__(self, model_name: str = "voyage-3"):
        import voyageai
        self.client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))
        self.model_name = model_name

    def get_embedding(self, text: str) -> List[float]:
        result = self.client.embed([text], model=self.model_name)
        return result.embeddings[0]

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        result = self.client.embed(texts, model=self.model_name)
        return result.embeddings


class GeminiEmbedding(EmbeddingProvider):
    """Google Gemini embedding provider."""

    def __init__(self, model_name: Optional[str] = None):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = model_name or os.getenv("GEMINI_EMBEDDING_MODEL_NAME", "models/embedding-001")
        self.genai = genai

    def get_embedding(self, text: str) -> List[float]:
        result = self.genai.embed_content(
            model=self.model_name,
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            result = self.genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document"
            )
            embeddings.append(result['embedding'])
        return embeddings


class LLMClient:
    """
    Unified LLM client supporting multiple providers.

    Supports:
    - OpenAI (GPT-4, GPT-4o)
    - Anthropic (Claude 3.5 Sonnet)
    - Google (Gemini 1.5 Pro)
    """

    def __init__(
        self,
        provider: str = "openai",
        model_name: Optional[str] = None,
        embedding_provider: str = "openai",
        embedding_model: Optional[str] = None,
        temperature: float = 0.7
    ):
        self.provider = provider.lower()
        self.temperature = temperature
        self.model_name = model_name
        self._llm = None
        self._embedding_client = None

        # Set model name from environment or default
        if self.provider == "openai":
            self.model_name = model_name or os.getenv("OPENAI_MODEL_NAME", "gpt-4o")
        elif self.provider == "anthropic":
            self.model_name = model_name or os.getenv("ANTHROPIC_MODEL_NAME", "claude-3-5-sonnet-20241022")
        elif self.provider == "google":
            self.model_name = model_name or os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro")

        # Initialize embedding provider
        embedding_provider = embedding_provider.lower()
        if embedding_provider == "openai":
            emb_model = embedding_model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
            self._embedding_client = OpenAIEmbedding(emb_model)
        elif embedding_provider == "voyage":
            emb_model = embedding_model or "voyage-3"
            self._embedding_client = VoyageEmbedding(emb_model)
        elif embedding_provider == "google":
            emb_model = embedding_model or os.getenv("GEMINI_EMBEDDING_MODEL_NAME", "models/embedding-001")
            self._embedding_client = GeminiEmbedding(emb_model)
        else:
            # Default to OpenAI
            self._embedding_client = OpenAIEmbedding()

        logger.info(f"LLMClient initialized: provider={self.provider}, model={self.model_name}, embedding={embedding_provider}")

    def _get_llm(self):
        """Lazy initialization of LLM."""
        if self._llm is None:
            if self.provider == "openai":
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(
                    model=self.model_name,
                    temperature=self.temperature,
                    api_key=os.getenv("OPENAI_API_KEY")
                )
            elif self.provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                self._llm = ChatAnthropic(
                    model=self.model_name,
                    temperature=self.temperature,
                    api_key=os.getenv("ANTHROPIC_API_KEY")
                )
            elif self.provider == "google":
                from langchain_google_genai import ChatGoogleGenerativeAI
                self._llm = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    temperature=self.temperature,
                    google_api_key=os.getenv("GEMINI_API_KEY")
                )
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        return self._llm

    def invoke(self, prompt: str) -> str:
        """Invoke LLM with a prompt."""
        llm = self._get_llm()
        response = llm.invoke(prompt)
        return response.content

    def chat_json(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict[str, Any]:
        """Chat with LLM and return JSON response."""
        import json

        # Combine messages into a single prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            else:
                prompt_parts.append(content)

        full_prompt = "\n\n".join(prompt_parts)

        llm = self._get_llm()
        response = llm.invoke(full_prompt)
        response_text = response.content

        # Try to parse JSON from response
        try:
            # Try to extract JSON from response
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()

            return json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            return {}

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text."""
        return self._embedding_client.get_embedding(text)

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts."""
        return self._embedding_client.get_embeddings_batch(texts)


def get_llm_client(
    agent_name: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    embedding_provider: Optional[str] = None,
    embedding_model: Optional[str] = None,
    temperature: float = 0.7
) -> LLMClient:
    """
    Get LLM client configured for specific agent.

    Args:
        agent_name: Agent name to load config from (news_trend_agent, viral_video_agent, social_trend_agent)
        provider: Override LLM provider
        model_name: Override model name
        embedding_provider: Override embedding provider
        embedding_model: Override embedding model
        temperature: LLM temperature

    Returns:
        Configured LLMClient instance
    """
    from src.core.config import get_config_manager

    cfg = get_config_manager()

    # Load agent-specific config if agent_name provided
    if agent_name:
        agent_cfg = cfg.get_agent_config(agent_name)
        if agent_cfg:
            if not provider and agent_cfg.llm:
                # agent_cfg.llm is LLMConfig object, use attribute access
                provider = str(agent_cfg.llm.provider) if agent_cfg.llm.provider else "openai"
                model_name = model_name or agent_cfg.llm.model_name
                temperature = agent_cfg.llm.temperature if agent_cfg.llm.temperature else temperature

            if not embedding_provider and agent_cfg.embedding:
                # agent_cfg.embedding is a dict
                embedding_provider = agent_cfg.embedding.get("provider", "openai")
                embedding_model = embedding_model or agent_cfg.embedding.get("model_name")

    # Defaults
    provider = provider or "openai"
    embedding_provider = embedding_provider or "openai"

    return LLMClient(
        provider=provider,
        model_name=model_name,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        temperature=temperature
    )


# Analysis helper functions
def analyze_sentiment_llm(text: str, client: Optional[LLMClient] = None) -> Dict[str, Any]:
    """Analyze sentiment using LLM."""
    if client is None:
        client = get_llm_client()

    prompt = f"""Analyze the sentiment of the following text and return a JSON object with:
- sentiment: "positive", "negative", or "neutral"
- confidence: float between 0 and 1
- key_phrases: list of key phrases that influenced the sentiment

Text: {text}

Return only valid JSON."""

    import json
    response = client.invoke(prompt)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"sentiment": "neutral", "confidence": 0.5, "key_phrases": []}


def extract_keywords_llm(text: str, max_keywords: int = 10, client: Optional[LLMClient] = None) -> List[str]:
    """Extract keywords using LLM."""
    if client is None:
        client = get_llm_client()

    prompt = f"""Extract the {max_keywords} most important keywords from the following text.
Return only a JSON array of strings.

Text: {text}

Return only valid JSON array."""

    import json
    response = client.invoke(prompt)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return []


def cluster_topics_llm(texts: List[str], num_clusters: int = 5, client: Optional[LLMClient] = None) -> Dict[str, List[int]]:
    """Cluster texts into topics using LLM."""
    if client is None:
        client = get_llm_client()

    texts_str = "\n".join([f"{i}: {t[:200]}" for i, t in enumerate(texts)])

    prompt = f"""Group the following texts into {num_clusters} topic clusters.
Return a JSON object where keys are topic names and values are arrays of text indices.

Texts:
{texts_str}

Return only valid JSON."""

    import json
    response = client.invoke(prompt)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"uncategorized": list(range(len(texts)))}


def generate_insights_llm(data: Dict[str, Any], client: Optional[LLMClient] = None) -> str:
    """Generate insights from data using LLM."""
    if client is None:
        client = get_llm_client()

    import json
    data_str = json.dumps(data, ensure_ascii=False, indent=2)

    prompt = f"""Based on the following data, generate actionable insights and recommendations.

Data:
{data_str}

Provide clear, concise insights in Korean."""

    return client.invoke(prompt)


class AnalysisResult:
    """Container for analysis results."""

    def __init__(
        self,
        sentiment: Optional[Dict[str, Any]] = None,
        keywords: Optional[List[str]] = None,
        topics: Optional[Dict[str, List[int]]] = None,
        insights: Optional[str] = None
    ):
        self.sentiment = sentiment or {}
        self.keywords = keywords or []
        self.topics = topics or {}
        self.insights = insights or ""


__all__ = [
    "LLMClient",
    "get_llm_client",
    "analyze_sentiment_llm",
    "extract_keywords_llm",
    "cluster_topics_llm",
    "generate_insights_llm",
    "AnalysisResult",
    "EmbeddingProvider",
    "OpenAIEmbedding",
    "VoyageEmbedding",
    "GeminiEmbedding",
]

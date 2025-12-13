"""
멀티 LLM 백엔드 클라이언트

지원 프로바이더:
- OpenAI
- Anthropic (Claude)
- Google (Gemini)
- Groq
- Azure OpenAI
- Ollama (Local)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, cast

logger = logging.getLogger(__name__)

# Global client instance
_llm_client = None


class LLMClient:
    """
    통합 LLM 클라이언트.

    여러 LLM 프로바이더를 추상화하여 동일한 인터페이스로 사용.
    """

    def __init__(self, provider: Optional[str] = None):
        """
        Args:
            provider: LLM 프로바이더 (openai, anthropic, google, groq, azure, ollama)
        """
        self.provider = provider or os.getenv("LLM_PROVIDER", "openai")
        self._client: Any = None
        self._model: str = ""
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the LLM client based on provider."""
        try:
            if self.provider == "openai":
                self._init_openai()
            elif self.provider == "anthropic":
                self._init_anthropic()
            elif self.provider == "google":
                self._init_google()
            elif self.provider == "groq":
                self._init_groq()
            elif self.provider == "azure":
                self._init_azure()
            elif self.provider == "ollama":
                self._init_ollama()
            else:
                logger.warning(f"Unknown provider: {self.provider}. Using OpenAI.")
                self._init_openai()

        except Exception as e:
            logger.error(f"Failed to initialize {self.provider} client: {e}")

    def _init_openai(self):
        """Initialize OpenAI client."""
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        self._client = OpenAI(api_key=api_key)
        # Ref: https://platform.openai.com/docs/models
        self._model = os.getenv("OPENAI_MODEL_NAME", "gpt-5.2")
        logger.info(f"OpenAI client initialized with model: {self._model}")

    def _init_anthropic(self):
        """Initialize Anthropic client."""
        from anthropic import Anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self._client = Anthropic(api_key=api_key)
        # Ref: https://docs.anthropic.com/en/docs/about-claude/models
        self._model = os.getenv("ANTHROPIC_MODEL_NAME", "claude-sonnet-4-5")
        logger.info(f"Anthropic client initialized with model: {self._model}")

    def _init_google(self):
        """Initialize Google Gemini client."""
        import google.generativeai as genai
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set")

        genai.configure(api_key=api_key)
        # Ref: https://ai.google.dev/gemini-api/docs/models
        self._model = os.getenv("GOOGLE_MODEL_NAME", "gemini-2.5-pro")
        self._client = genai.GenerativeModel(self._model)
        logger.info(f"Google client initialized with model: {self._model}")

    def _init_groq(self):
        """Initialize Groq client."""
        from groq import Groq  # type: ignore[import]
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set")

        self._client = Groq(api_key=api_key)
        self._model = os.getenv("GROQ_MODEL_NAME", "llama-3.1-70b-versatile")
        logger.info(f"Groq client initialized with model: {self._model}")

    def _init_azure(self):
        """Initialize Azure OpenAI client."""
        from openai import AzureOpenAI
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

        if not api_key or not endpoint:
            raise ValueError("Azure OpenAI credentials not set")

        self._client = AzureOpenAI(
            api_key=api_key,
            # Azure OpenAI data-plane inference api-version (GA)
            # Ref: https://learn.microsoft.com/en-us/azure/ai-services/openai/reference
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            azure_endpoint=endpoint,
        )
        # NOTE: Azure OpenAI는 model이 아니라 "deployment name"을 사용합니다.
        self._model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5.2")
        logger.info("Azure OpenAI client initialized")

    def _init_ollama(self):
        """Initialize Ollama client."""
        from openai import OpenAI
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        self._client = OpenAI(
            base_url=f"{base_url}/v1",
            api_key="ollama",  # Ollama doesn't need a real key
        )
        self._model = os.getenv("OLLAMA_MODEL_NAME", "llama3.1")
        logger.info(f"Ollama client initialized with model: {self._model}")

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """
        LLM에 메시지 전송.

        Args:
            messages: 메시지 리스트 [{"role": "user", "content": "..."}]
            temperature: 생성 온도
            max_tokens: 최대 토큰 수
            json_mode: JSON 출력 모드

        Returns:
            LLM 응답 텍스트
        """
        if self._client is None:
            raise ValueError("LLM client not initialized")

        try:
            if self.provider in ["openai", "azure", "groq", "ollama"]:
                return self._chat_openai_compatible(
                    messages, temperature, max_tokens, json_mode, **kwargs
                )
            elif self.provider == "anthropic":
                return self._chat_anthropic(
                    messages, temperature, max_tokens, **kwargs
                )
            elif self.provider == "google":
                return self._chat_google(
                    messages, temperature, max_tokens, **kwargs
                )
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

        except Exception as e:
            logger.error(f"LLM chat error: {e}")
            raise

    def _chat_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        **kwargs
    ) -> str:
        """Chat with OpenAI-compatible APIs."""
        client = cast(Any, self._client)
        if client is None:
            raise ValueError("LLM client not initialized")
        # Allow overriding parameters (e.g., model) via kwargs
        effective_model = kwargs.get("model", self._model)

        params: Dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "temperature": temperature,
        }

        # Some newer OpenAI models require `max_completion_tokens` instead of `max_tokens`.
        # We'll choose the right parameter based on model name.
        # - o-series: o1/o3/o4...
        # - GPT-5 family: gpt-5.*
        if isinstance(effective_model, str) and effective_model.startswith(("o", "gpt-5")):
            params["max_completion_tokens"] = max_tokens
        else:
            params["max_tokens"] = max_tokens

        if json_mode and self.provider in ["openai", "azure"]:
            params["response_format"] = {"type": "json_object"}

        # Allow overriding parameters (e.g., model) via kwargs
        params.update(kwargs)

        try:
            response = client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            msg = str(e)

            # Retry with max_completion_tokens if API rejects max_tokens
            if "max_tokens" in msg and "max_completion_tokens" in msg and "max_tokens" in params:
                params.pop("max_tokens", None)
                params["max_completion_tokens"] = max_tokens
                response = client.chat.completions.create(**params)
                return response.choices[0].message.content

            # If the project doesn't have access to the requested model, fall back to default.
            if ("does not have access to model" in msg or "model_not_found" in msg) and effective_model != self._model:
                logger.warning(
                    f"Model access error for '{effective_model}'. Falling back to default model '{self._model}'."
                )
                params["model"] = self._model
                # Ensure token param matches fallback model
                params.pop("max_completion_tokens", None)
                params["max_tokens"] = max_tokens
                response = client.chat.completions.create(**params)
                return response.choices[0].message.content

            raise

    def _chat_anthropic(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """Chat with Anthropic API."""
        client = cast(Any, self._client)
        if client is None:
            raise ValueError("LLM client not initialized")
        # Convert to Anthropic format
        system_message = ""
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        response = client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_message,
            messages=anthropic_messages,
        )

        return response.content[0].text

    def _chat_google(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """Chat with Google Gemini API."""
        client = cast(Any, self._client)
        if client is None:
            raise ValueError("LLM client not initialized")
        # Convert to Gemini format
        gemini_messages = []
        for msg in messages:
            role = "user" if msg["role"] in ["user", "system"] else "model"
            gemini_messages.append({
                "role": role,
                "parts": [{"text": msg["content"]}],
            })

        response = client.generate_content(
            gemini_messages,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )

        return response.text

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        JSON 형식으로 응답 받기.

        Args:
            messages: 메시지 리스트
            schema: 기대하는 JSON 스키마 (프롬프트에 포함됨)
            temperature: 생성 온도 (낮을수록 일관성 높음)

        Returns:
            파싱된 JSON 딕셔너리
        """
        # Add schema instruction if provided
        if schema:
            schema_instruction = f"\n\nRespond with JSON in this exact format:\n```json\n{json.dumps(schema, indent=2)}\n```"
            if messages and messages[-1]["role"] == "user":
                messages[-1]["content"] += schema_instruction
            else:
                messages.append({
                    "role": "user",
                    "content": f"Return your response as JSON in this format:\n{json.dumps(schema, indent=2)}"
                })

        response = self.chat(
            messages,
            temperature=temperature,
            json_mode=True,
            **kwargs
        )

        # Parse JSON from response
        try:
            # Try to extract JSON from markdown code block
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                json_str = response

            return json.loads(json_str.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response}")
            raise ValueError(f"Invalid JSON response: {e}")

    def get_embedding(self, text: str) -> List[float]:
        """
        텍스트 임베딩 생성.

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터
        """
        if self.provider in ["openai", "azure"]:
            model = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-large")
            client = cast(Any, self._client)
            if client is None:
                raise ValueError("LLM client not initialized")
            response = client.embeddings.create(
                model=model,
                input=text,
            )
            return response.data[0].embedding

        else:
            # Fallback to OpenAI for embeddings
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-large")
            response = client.embeddings.create(model=model, input=text)
            return response.data[0].embedding

    def get_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        배치로 임베딩 생성.

        Args:
            texts: 텍스트 리스트
            batch_size: 배치 크기

        Returns:
            임베딩 벡터 리스트
        """
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            if self.provider in ["openai", "azure"]:
                model = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-large")
                client = cast(Any, self._client)
                if client is None:
                    raise ValueError("LLM client not initialized")
                response = client.embeddings.create(
                    model=model,
                    input=batch,
                )
                batch_embeddings = [item.embedding for item in response.data]
            else:
                # Fallback
                batch_embeddings = [self.get_embedding(text) for text in batch]

            embeddings.extend(batch_embeddings)

        return embeddings


def get_llm_client(provider: Optional[str] = None) -> LLMClient:
    """
    Get LLM client instance (singleton).

    Note:
        - provider 인자를 넘기면 해당 프로바이더로 새 클라이언트를 생성합니다.
        - 에이전트별 설정을 사용할 때는 src.core.config의 ConfigManager로
          provider를 결정한 뒤 이 함수에 전달하는 패턴을 권장합니다.
    """
    global _llm_client
    if _llm_client is None or (provider and _llm_client.provider != provider):
        _llm_client = LLMClient(provider)
    return _llm_client

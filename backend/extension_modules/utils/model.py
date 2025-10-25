"""
Cloud-neutral LLM model utility
Supports multiple LLM providers: Azure OpenAI, OpenAI, Anthropic, Google, Ollama
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LLM Provider Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "azure_openai")

# OpenAI / Azure OpenAI Configuration (unified naming)
OPENAI_API_TYPE = os.getenv("OPENAI_API_TYPE", "azure")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION", "2024-02-15-preview")
OPENAI_DEPLOYMENT_NAME = os.getenv("OPENAI_DEPLOYMENT_NAME", "gpt-4")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4")

# Anthropic Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL_NAME = os.getenv("ANTHROPIC_MODEL_NAME", "claude-3-5-sonnet-20241022")

# Google Gemini Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_MODEL_NAME = os.getenv("GOOGLE_MODEL_NAME", "gemini-1.5-pro")

# Ollama Configuration (Local LLM)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "llama3.2")


def mk_model(temperature: float = 0.1, max_tokens: int = 2000):
    """
    Create LLM model instance based on LLM_PROVIDER

    Args:
        temperature: Model temperature (0.0-1.0)
        max_tokens: Maximum tokens in response

    Returns:
        LLM model instance (LangChain compatible)

    Raises:
        RuntimeError: If provider is not supported or configuration is missing
    """
    provider = LLM_PROVIDER.lower()

    print(f"[LLM] Creating model with provider: {provider}")

    if provider == "azure_openai":
        return _create_azure_openai_model(temperature, max_tokens)
    elif provider == "openai":
        return _create_openai_model(temperature, max_tokens)
    elif provider == "anthropic":
        return _create_anthropic_model(temperature, max_tokens)
    elif provider == "google":
        return _create_google_model(temperature, max_tokens)
    elif provider == "ollama":
        return _create_ollama_model(temperature, max_tokens)
    else:
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER: {provider}. "
            f"Supported: azure_openai, openai, anthropic, google, ollama"
        )


def _create_azure_openai_model(temperature: float, max_tokens: int):
    """Create Azure OpenAI model"""
    try:
        from langchain_openai import AzureChatOpenAI
    except ImportError as e:
        raise RuntimeError(
            f"langchain-openai not installed. Run: pip install langchain-openai ({e})"
        )

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for Azure OpenAI")
    if not OPENAI_API_BASE:
        raise RuntimeError("OPENAI_API_BASE is required for Azure OpenAI")

    model = AzureChatOpenAI(
        azure_endpoint=OPENAI_API_BASE,
        azure_deployment=OPENAI_DEPLOYMENT_NAME,
        api_version=OPENAI_API_VERSION,
        api_key=OPENAI_API_KEY,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    print(f"[LLM] Azure OpenAI model created: {OPENAI_DEPLOYMENT_NAME}")
    return model


def _create_openai_model(temperature: float, max_tokens: int):
    """Create OpenAI model"""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        raise RuntimeError(
            f"langchain-openai not installed. Run: pip install langchain-openai ({e})"
        )

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for OpenAI")

    model = ChatOpenAI(
        api_key=OPENAI_API_KEY,
        model=OPENAI_MODEL_NAME,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    print(f"[LLM] OpenAI model created: {OPENAI_MODEL_NAME}")
    return model


def _create_anthropic_model(temperature: float, max_tokens: int):
    """Create Anthropic Claude model"""
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as e:
        raise RuntimeError(
            f"langchain-anthropic not installed. Run: pip install langchain-anthropic ({e})"
        )

    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is required for Anthropic")

    model = ChatAnthropic(
        api_key=ANTHROPIC_API_KEY,
        model=ANTHROPIC_MODEL_NAME,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    print(f"[LLM] Anthropic model created: {ANTHROPIC_MODEL_NAME}")
    return model


def _create_google_model(temperature: float, max_tokens: int):
    """Create Google Gemini model"""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as e:
        raise RuntimeError(
            f"langchain-google-genai not installed. Run: pip install langchain-google-genai ({e})"
        )

    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is required for Google Gemini")

    model = ChatGoogleGenerativeAI(
        google_api_key=GOOGLE_API_KEY,
        model=GOOGLE_MODEL_NAME,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )

    print(f"[LLM] Google Gemini model created: {GOOGLE_MODEL_NAME}")
    return model


def _create_ollama_model(temperature: float, max_tokens: int):
    """Create Ollama model (Local LLM)"""
    try:
        from langchain_community.chat_models import ChatOllama
    except ImportError as e:
        raise RuntimeError(
            f"langchain-community not installed. Run: pip install langchain-community ({e})"
        )

    model = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_MODEL_NAME,
        temperature=temperature,
    )

    print(f"[LLM] Ollama model created: {OLLAMA_MODEL_NAME} at {OLLAMA_BASE_URL}")
    return model


def get_model_info():
    """Get current model configuration info"""
    return {
        "provider": LLM_PROVIDER,
        "model_name": {
            "azure_openai": OPENAI_DEPLOYMENT_NAME,
            "openai": OPENAI_MODEL_NAME,
            "anthropic": ANTHROPIC_MODEL_NAME,
            "google": GOOGLE_MODEL_NAME,
            "ollama": OLLAMA_MODEL_NAME,
        }.get(LLM_PROVIDER.lower(), "unknown"),
        "api_base": OPENAI_API_BASE if LLM_PROVIDER.lower() in ["azure_openai", "openai"] else None,
    }

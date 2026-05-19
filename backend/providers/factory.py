"""
providers/factory.py
Resolves which provider to instantiate based on config.
Everything else in the system calls get_provider() — nothing else.
"""

from functools import lru_cache
from .base      import BaseProvider
from .anthropic import AnthropicProvider
from .openai    import OpenAIProvider
from .gemini    import GeminiProvider
from .b3gpt     import B3GPTProvider


@lru_cache(maxsize=1)
def get_provider() -> BaseProvider:
    """
    Singleton provider. Reads from environment at first call.
    Change AI_PROVIDER in .env and restart — nothing else changes.
    """
    from utils.config import settings

    provider = settings.AI_PROVIDER.lower()

    if provider == "anthropic":
        return AnthropicProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            base_url=settings.AI_BASE_URL,
        )
    elif provider in ("openai", "b3gpt"):
        base_url = settings.effective_base_url
        if not base_url:
            raise ValueError(
                "AI_PROVIDER=b3gpt requer BASE_URL ou AI_BASE_URL definido no .env"
            )
        return B3GPTProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            base_url=base_url,
            timeout=int(settings.ENGINE_TIMEOUT),
        )
    elif provider == "gemini":
        return GeminiProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            base_url=settings.AI_BASE_URL,
        )
    else:
        raise ValueError(
            f"Unknown AI_PROVIDER='{provider}'. "
            f"Valid options: anthropic | openai | b3gpt | gemini"
        )

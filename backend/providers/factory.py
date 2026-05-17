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
from .corporate import CorporateProvider


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
    elif provider == "openai":
        return OpenAIProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            base_url=settings.AI_BASE_URL,
        )
    elif provider == "gemini":
        return GeminiProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            base_url=settings.AI_BASE_URL,
        )
    elif provider == "corporate":
        return CorporateProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            base_url=settings.AI_BASE_URL or "",
        )
    else:
        raise ValueError(
            f"Unknown AI_PROVIDER='{provider}'. "
            f"Valid options: anthropic | openai | gemini | corporate"
        )

"""
providers/base.py
Abstract interface for all AI providers.
Engines call provider.complete() — they never know which AI is underneath.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CompletionRequest:
    prompt:     str
    max_tokens: int  = 1500
    temperature: float = 0.2   # low for deterministic QA analysis


@dataclass
class CompletionResponse:
    content:    str
    model:      str
    input_tokens:  int = 0
    output_tokens: int = 0


class BaseProvider(ABC):

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a prompt, get a response. That's the entire contract."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Returns True if the provider is reachable."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

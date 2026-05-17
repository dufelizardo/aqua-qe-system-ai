"""
providers/anthropic.py
Claude (Anthropic) provider implementation.
"""

import httpx
from .base import BaseProvider, CompletionRequest, CompletionResponse


class AnthropicProvider(BaseProvider):

    BASE_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self._api_key = api_key
        self._model   = model
        self._base_url = base_url or self.BASE_URL

    @property
    def provider_name(self) -> str: return "anthropic"

    @property
    def model_name(self) -> str: return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        headers = {
            "x-api-key":         self._api_key,
            "anthropic-version": self.API_VERSION,
            "content-type":      "application/json",
        }
        payload = {
            "model":      self._model,
            "max_tokens": request.max_tokens,
            "messages":   [{"role": "user", "content": request.prompt}],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self._base_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )
        usage = data.get("usage", {})
        return CompletionResponse(
            content=content,
            model=data.get("model", self._model),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

    async def health_check(self) -> bool:
        try:
            resp = await self.complete(CompletionRequest(prompt="ping", max_tokens=5))
            return bool(resp.content)
        except Exception:
            return False

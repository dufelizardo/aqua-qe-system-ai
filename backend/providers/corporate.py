"""
providers/corporate.py
Corporate AI provider — works with any internal proxy that exposes
an OpenAI-compatible API (most enterprise gateways do).

Set in .env:
    AI_PROVIDER=corporate
    AI_BASE_URL=https://ai-gateway.yourcompany.com/v1/chat/completions
    AI_API_KEY=your-internal-key
    AI_MODEL=gpt-4o  (or whatever your gateway exposes)
"""

import httpx
from .base import BaseProvider, CompletionRequest, CompletionResponse


class CorporateProvider(BaseProvider):
    """
    OpenAI-compatible wrapper for internal corporate AI gateways.
    No code changes needed when switching models or endpoints —
    just update .env / Kubernetes secrets.
    """

    def __init__(self, api_key: str, model: str, base_url: str):
        if not base_url:
            raise ValueError("CorporateProvider requires AI_BASE_URL in .env")
        self._api_key  = api_key
        self._model    = model
        self._base_url = base_url

    @property
    def provider_name(self) -> str: return "corporate"

    @property
    def model_name(self) -> str: return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
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

        # Handle both OpenAI format and raw text responses
        if "choices" in data:
            content = data["choices"][0]["message"]["content"]
        elif "content" in data:
            content = data["content"]
        else:
            content = str(data)

        usage = data.get("usage", {})
        return CompletionResponse(
            content=content,
            model=self._model,
            input_tokens=usage.get("prompt_tokens", usage.get("input_tokens", 0)),
            output_tokens=usage.get("completion_tokens", usage.get("output_tokens", 0)),
        )

    async def health_check(self) -> bool:
        try:
            resp = await self.complete(CompletionRequest(prompt="ping", max_tokens=5))
            return bool(resp.content)
        except Exception:
            return False

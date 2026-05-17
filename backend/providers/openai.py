"""
providers/openai.py
OpenAI (GPT-4/o) provider implementation.
Also works for Azure OpenAI — just set base_url to your Azure endpoint.
"""

import httpx
from .base import BaseProvider, CompletionRequest, CompletionResponse


class OpenAIProvider(BaseProvider):

    BASE_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self._api_key  = api_key
        self._model    = model
        self._base_url = base_url or self.BASE_URL

    @property
    def provider_name(self) -> str: return "openai"

    @property
    def model_name(self) -> str: return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
        }
        payload = {
            "model":       self._model,
            "max_tokens":  request.max_tokens,
            "temperature": request.temperature,
            "messages":    [{"role": "user", "content": request.prompt}],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self._base_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage   = data.get("usage", {})
        return CompletionResponse(
            content=content,
            model=data.get("model", self._model),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )

    async def health_check(self) -> bool:
        try:
            resp = await self.complete(CompletionRequest(prompt="ping", max_tokens=5))
            return bool(resp.content)
        except Exception:
            return False

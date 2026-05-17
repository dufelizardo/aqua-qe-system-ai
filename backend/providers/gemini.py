"""
providers/gemini.py
Google Gemini provider — compatible with Google AI Studio API keys.

Set in .env:
    AI_PROVIDER=gemini
    AI_MODEL=gemini-2.0-flash
    AI_API_KEY=your-google-ai-studio-key
"""

import httpx
from .base import BaseProvider, CompletionRequest, CompletionResponse


class GeminiProvider(BaseProvider):

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self._api_key  = api_key
        self._model    = model
        self._base_url = base_url or self.BASE_URL

    @property
    def provider_name(self) -> str: return "gemini"

    @property
    def model_name(self) -> str: return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        url = f"{self._base_url}/{self._model}:generateContent?key={self._api_key}"

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": request.prompt}]}
            ],
            "generationConfig": {
                "maxOutputTokens": request.max_tokens,
                "temperature":     request.temperature,
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Extract text from Gemini response structure
        try:
            content = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Unexpected Gemini response structure: {data}") from e

        usage = data.get("usageMetadata", {})
        return CompletionResponse(
            content=content,
            model=self._model,
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
        )

    async def health_check(self) -> bool:
        try:
            resp = await self.complete(CompletionRequest(prompt="ping", max_tokens=5))
            return bool(resp.content)
        except Exception:
            return False

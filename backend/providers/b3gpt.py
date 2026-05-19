"""
providers/b3gpt.py
B3GPT Provider — Azure OpenAI compatible

Endpoint: {BASE_URL}/deployments/{model_name}/chat/completions
Auth: api-key header

.env config:
  AI_PROVIDER=b3gpt
  AI_MODEL=<model-name>
  AI_API_KEY=<your token>
  BASE_URL=<your corporate endpoint>
"""

import httpx
from providers.base import BaseProvider, CompletionRequest, CompletionResponse


class B3GPTProvider(BaseProvider):

    def __init__(self, api_key: str, model: str, base_url: str, timeout: int = 120):
        self.api_key  = api_key
        self.model    = model
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout

    @property
    def provider_name(self) -> str:
        return "b3gpt"

    @property
    def model_name(self) -> str:
        return self.model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        url = f"{self.base_url}/deployments/{self.model}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "api-key":      self.api_key,
        }

        body = {
            "messages": [
                {"role": "user", "content": request.prompt}
            ],
            "max_tokens":   request.max_tokens or 2000,
            "temperature":  request.temperature or 0.3,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        content = (
            data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
        )

        return CompletionResponse(content=content)

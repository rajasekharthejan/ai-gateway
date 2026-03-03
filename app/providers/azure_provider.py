"""Azure OpenAI provider implementation using httpx."""

import logging
import time

import httpx

from app.config import get_settings
from app.providers.base import BaseProvider
from app.schemas.gateway import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    GatewayMetadata,
    TokenUsage,
)

logger = logging.getLogger(__name__)

# Mapping from OpenAI model names to Azure deployment names.
# Adjust to match your actual Azure deployment names.
DEFAULT_DEPLOYMENT_MAP: dict[str, str] = {
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4-turbo": "gpt-4-turbo",
    "gpt-4": "gpt-4",
    "gpt-35-turbo": "gpt-35-turbo",
    "gpt-3.5-turbo": "gpt-35-turbo",
}


class AzureOpenAIProvider(BaseProvider):
    provider_name = "azure"

    def __init__(self) -> None:
        settings = get_settings()
        self.endpoint = settings.AZURE_OPENAI_ENDPOINT.rstrip("/")
        self.api_key = settings.AZURE_OPENAI_KEY
        self.api_version = settings.AZURE_OPENAI_API_VERSION
        self.deployment_map = dict(DEFAULT_DEPLOYMENT_MAP)

        self.client = httpx.AsyncClient(
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    def _resolve_deployment(self, model: str) -> str:
        return self.deployment_map.get(model, model)

    def supports_model(self, model: str) -> bool:
        if model in self.deployment_map:
            return True
        return any(model.startswith(prefix) for prefix in ("gpt-",))

    async def is_available(self) -> bool:
        return bool(self.endpoint and self.api_key)

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        start_time = time.monotonic()
        deployment = self._resolve_deployment(request.model)

        url = (
            f"{self.endpoint}/openai/deployments/{deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )

        payload = {
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "n": request.n,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.stop is not None:
            payload["stop"] = request.stop
        if request.presence_penalty != 0.0:
            payload["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty != 0.0:
            payload["frequency_penalty"] = request.frequency_penalty
        if request.tools is not None:
            payload["tools"] = request.tools
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice
        if request.response_format is not None:
            payload["response_format"] = request.response_format

        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        latency_ms = int((time.monotonic() - start_time) * 1000)

        choices = []
        for c in data.get("choices", []):
            msg = c.get("message", {})
            choices.append(
                ChatCompletionChoice(
                    index=c.get("index", 0),
                    message=ChatMessage(
                        role=msg.get("role", "assistant"),
                        content=msg.get("content"),
                        tool_calls=msg.get("tool_calls"),
                    ),
                    finish_reason=c.get("finish_reason"),
                )
            )

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return ChatCompletionResponse(
            id=data.get("id", ""),
            object=data.get("object", "chat.completion"),
            created=data.get("created", int(time.time())),
            model=data.get("model", request.model),
            choices=choices,
            usage=usage,
            gateway_metadata=GatewayMetadata(
                provider=self.provider_name,
                latency_ms=latency_ms,
            ),
        )

    async def close(self) -> None:
        await self.client.aclose()

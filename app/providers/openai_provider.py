"""OpenAI API provider implementation using httpx."""

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

OPENAI_MODELS = {
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-4-0125-preview",
    "gpt-4-1106-preview",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo-1106",
    "o1",
    "o1-mini",
    "o1-preview",
    "o3-mini",
}

OPENAI_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(BaseProvider):
    provider_name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.OPENAI_API_KEY
        self.client = httpx.AsyncClient(
            base_url=OPENAI_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    def supports_model(self, model: str) -> bool:
        if model in OPENAI_MODELS:
            return True
        return any(model.startswith(prefix) for prefix in ("gpt-", "o1", "o3"))

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        start_time = time.monotonic()

        payload = {
            "model": request.model,
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
        if request.user is not None:
            payload["user"] = request.user
        if request.tools is not None:
            payload["tools"] = request.tools
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        if request.seed is not None:
            payload["seed"] = request.seed

        response = await self.client.post("/chat/completions", json=payload)
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

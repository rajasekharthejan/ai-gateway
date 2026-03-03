"""AWS Bedrock provider implementation for Claude models."""

import json
import logging
import time
import uuid as uuid_mod
from typing import Any

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

# Mapping from friendly model names to Bedrock model IDs
BEDROCK_MODEL_MAP: dict[str, str] = {
    "claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "claude-3-5-haiku": "anthropic.claude-3-5-haiku-20241022-v1:0",
    "claude-3-opus": "anthropic.claude-3-opus-20240229-v1:0",
    "claude-3-sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
    "claude-3-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
}


def _openai_messages_to_bedrock(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Convert OpenAI-style messages to Bedrock Converse format.

    Returns (system_prompt, bedrock_messages).
    """
    system_prompt: str | None = None
    bedrock_messages: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            system_prompt = content if isinstance(content, str) else str(content)
            continue

        bedrock_role = "user" if role == "user" else "assistant"
        if isinstance(content, str):
            bedrock_messages.append(
                {"role": bedrock_role, "content": [{"text": content}]}
            )
        elif isinstance(content, list):
            parts = []
            for part in content:
                if part.get("type") == "text":
                    parts.append({"text": part["text"]})
            bedrock_messages.append({"role": bedrock_role, "content": parts})
        else:
            bedrock_messages.append(
                {"role": bedrock_role, "content": [{"text": str(content)}]}
            )

    return system_prompt, bedrock_messages


class BedrockProvider(BaseProvider):
    provider_name = "bedrock"

    def __init__(self) -> None:
        settings = get_settings()
        self.aws_access_key = settings.AWS_ACCESS_KEY_ID
        self.aws_secret_key = settings.AWS_SECRET_ACCESS_KEY
        self.region = settings.AWS_REGION
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
            )
        return self._client

    def _resolve_model_id(self, model: str) -> str:
        if model in BEDROCK_MODEL_MAP:
            return BEDROCK_MODEL_MAP[model]
        for prefix, model_id in BEDROCK_MODEL_MAP.items():
            if model.startswith(prefix):
                return model_id
        return model

    def supports_model(self, model: str) -> bool:
        if model in BEDROCK_MODEL_MAP:
            return True
        return any(model.startswith(p) for p in ("claude", "anthropic.claude"))

    async def is_available(self) -> bool:
        return bool(self.aws_access_key and self.aws_secret_key)

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        import asyncio

        start_time = time.monotonic()
        model_id = self._resolve_model_id(request.model)

        raw_messages = [m.model_dump(exclude_none=True) for m in request.messages]
        system_prompt, bedrock_messages = _openai_messages_to_bedrock(raw_messages)

        inference_config: dict[str, Any] = {
            "temperature": request.temperature,
            "topP": request.top_p,
        }
        if request.max_tokens is not None:
            inference_config["maxTokens"] = request.max_tokens
        else:
            inference_config["maxTokens"] = 4096

        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": bedrock_messages,
            "inferenceConfig": inference_config,
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        loop = asyncio.get_event_loop()
        client = self._get_client()
        response = await loop.run_in_executor(
            None, lambda: client.converse(**kwargs)
        )

        latency_ms = int((time.monotonic() - start_time) * 1000)

        output = response.get("output", {})
        message = output.get("message", {})
        content_blocks = message.get("content", [])

        text_parts = []
        for block in content_blocks:
            if "text" in block:
                text_parts.append(block["text"])

        assistant_text = "\n".join(text_parts) if text_parts else ""

        stop_reason = response.get("stopReason", "end_turn")
        finish_reason_map = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
            "tool_use": "tool_calls",
        }
        finish_reason = finish_reason_map.get(stop_reason, "stop")

        usage_data = response.get("usage", {})
        prompt_tokens = usage_data.get("inputTokens", 0)
        completion_tokens = usage_data.get("outputTokens", 0)

        choices = [
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=assistant_text),
                finish_reason=finish_reason,
            )
        ]

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid_mod.uuid4().hex[:24]}",
            created=int(time.time()),
            model=request.model,
            choices=choices,
            usage=usage,
            gateway_metadata=GatewayMetadata(
                provider=self.provider_name,
                latency_ms=latency_ms,
            ),
        )

    async def close(self) -> None:
        self._client = None

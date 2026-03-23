"""Tests for provider routing logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.router import ProviderRouter
from app.schemas.gateway import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    TokenUsage,
)


def make_mock_provider(name: str, models: list[str], should_fail: bool = False):
    provider = AsyncMock()
    provider.provider_name = name
    provider.supports_model = lambda m: m in models
    provider.is_available = AsyncMock(return_value=True)

    if should_fail:
        provider.chat_completion = AsyncMock(
            side_effect=RuntimeError(f"{name} failed")
        )
    else:
        provider.chat_completion = AsyncMock(
            return_value=ChatCompletionResponse(
                id="test-id",
                created=1700000000,
                model="gpt-4o",
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content="Hello!"),
                        finish_reason="stop",
                    )
                ],
                usage=TokenUsage(
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                ),
            )
        )
    return provider


def make_request(model: str = "gpt-4o") -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model=model,
        messages=[ChatMessage(role="user", content="hi")],
    )


class TestProviderRouter:
    def test_get_providers_for_model(self):
        router = ProviderRouter()
        router._providers = [
            make_mock_provider("openai", ["gpt-4o", "gpt-4o-mini"]),
            make_mock_provider("bedrock", ["claude-3-5-sonnet"]),
        ]
        router._initialized = True

        # OpenAI model
        providers = router._get_providers_for_model("gpt-4o")
        assert len(providers) == 1
        assert providers[0].provider_name == "openai"

        # Claude model
        providers = router._get_providers_for_model("claude-3-5-sonnet")
        assert len(providers) == 1
        assert providers[0].provider_name == "bedrock"

    def test_no_provider_for_unknown_model(self):
        router = ProviderRouter()
        router._providers = [
            make_mock_provider("openai", ["gpt-4o"]),
        ]
        router._initialized = True

        providers = router._get_providers_for_model("unknown-model")
        assert len(providers) == 0

    @pytest.mark.asyncio
    async def test_route_request_success(self):
        router = ProviderRouter()
        router._providers = [
            make_mock_provider("openai", ["gpt-4o"]),
        ]
        router._initialized = True

        response = await router.route_request(make_request("gpt-4o"))
        assert response.id == "test-id"
        assert response.choices[0].message.content == "Hello!"

    @pytest.mark.asyncio
    async def test_failover_on_provider_error(self):
        """If first provider fails, it should try the next one."""
        router = ProviderRouter()
        router._providers = [
            make_mock_provider("openai", ["gpt-4o"], should_fail=True),
            make_mock_provider("azure", ["gpt-4o"]),
        ]
        router._initialized = True

        response = await router.route_request(make_request("gpt-4o"))
        assert response.id == "test-id"

    @pytest.mark.asyncio
    async def test_all_providers_fail(self):
        router = ProviderRouter()
        router._providers = [
            make_mock_provider("openai", ["gpt-4o"], should_fail=True),
        ]
        router._initialized = True

        with pytest.raises(RuntimeError, match="All providers failed"):
            await router.route_request(make_request("gpt-4o"))

    @pytest.mark.asyncio
    async def test_no_provider_available(self):
        router = ProviderRouter()
        router._providers = []
        router._initialized = True

        with pytest.raises(RuntimeError, match="No provider available"):
            await router.route_request(make_request("gpt-4o"))

    def test_claude_prefers_bedrock(self):
        router = ProviderRouter()
        router._providers = [
            make_mock_provider("openai", ["gpt-4o", "claude-3-5-sonnet"]),
            make_mock_provider("bedrock", ["claude-3-5-sonnet"]),
        ]
        router._initialized = True

        providers = router._get_providers_for_model("claude-3-5-sonnet")
        assert providers[0].provider_name == "bedrock"

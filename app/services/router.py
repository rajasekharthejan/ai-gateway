"""Provider routing logic with failover and round-robin load balancing."""

import logging
from itertools import cycle

from app.config import get_settings
from app.providers.azure_provider import AzureOpenAIProvider
from app.providers.base import BaseProvider
from app.providers.bedrock_provider import BedrockProvider
from app.providers.openai_provider import OpenAIProvider
from app.schemas.gateway import ChatCompletionRequest, ChatCompletionResponse

logger = logging.getLogger(__name__)


class ProviderRouter:
    """Routes requests to the appropriate LLM provider with failover."""

    def __init__(self) -> None:
        self._providers: list[BaseProvider] = []
        self._round_robin: dict[str, cycle] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all provider clients and check availability."""
        if self._initialized:
            return

        settings = get_settings()

        providers_to_try: list[BaseProvider] = [
            OpenAIProvider(),
            AzureOpenAIProvider(),
            BedrockProvider(),
        ]

        for provider in providers_to_try:
            if await provider.is_available():
                self._providers.append(provider)
                logger.info("Provider %s is available", provider.provider_name)
            else:
                logger.info("Provider %s is not configured, skipping", provider.provider_name)
                await provider.close()

        self._initialized = True
        logger.info("Provider router initialized with %d providers", len(self._providers))

    def _get_providers_for_model(self, model: str) -> list[BaseProvider]:
        """Return all providers that support the given model, ordered by preference."""
        matching = [p for p in self._providers if p.supports_model(model)]

        # Preferred ordering: direct match providers first
        preferred_order = {
            "openai": 1,
            "azure": 2,
            "bedrock": 3,
        }

        # For Claude models, prefer Bedrock
        if model.startswith("claude"):
            preferred_order = {"bedrock": 1, "openai": 2, "azure": 3}

        matching.sort(key=lambda p: preferred_order.get(p.provider_name, 99))
        return matching

    def _get_next_provider(self, model: str) -> BaseProvider | None:
        """Get the next provider using round-robin for load balancing."""
        providers = self._get_providers_for_model(model)
        if not providers:
            return None

        key = model
        if key not in self._round_robin:
            self._round_robin[key] = cycle(providers)

        return next(self._round_robin[key])

    async def route_request(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Route a request to the best available provider, with failover.

        Raises RuntimeError if no provider can serve the request.
        """
        providers = self._get_providers_for_model(request.model)
        if not providers:
            raise RuntimeError(
                f"No provider available for model '{request.model}'. "
                f"Available providers: {[p.provider_name for p in self._providers]}"
            )

        last_error: Exception | None = None
        for provider in providers:
            try:
                logger.info(
                    "Routing model=%s to provider=%s",
                    request.model,
                    provider.provider_name,
                )
                response = await provider.chat_completion(request)
                return response
            except Exception as exc:
                logger.warning(
                    "Provider %s failed for model %s: %s",
                    provider.provider_name,
                    request.model,
                    str(exc),
                )
                last_error = exc
                continue

        raise RuntimeError(
            f"All providers failed for model '{request.model}'. "
            f"Last error: {last_error}"
        )

    def get_provider_name_for_model(self, model: str) -> str:
        """Return the name of the preferred provider for a model (for logging)."""
        providers = self._get_providers_for_model(model)
        if providers:
            return providers[0].provider_name
        return "unknown"

    async def close(self) -> None:
        """Shut down all provider clients."""
        for provider in self._providers:
            await provider.close()
        self._providers.clear()
        self._round_robin.clear()
        self._initialized = False


# Module-level singleton
provider_router = ProviderRouter()

"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod

from app.schemas.gateway import ChatCompletionRequest, ChatCompletionResponse


class BaseProvider(ABC):
    """Interface that all LLM provider adapters must implement."""

    provider_name: str = "base"

    @abstractmethod
    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Send a chat completion request and return a normalized response."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check whether this provider is configured and reachable."""
        ...

    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """Return True if this provider can serve the given model name."""
        ...

    async def close(self) -> None:
        """Clean up resources (HTTP clients, etc.)."""
        pass

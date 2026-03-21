"""Tests for Pydantic request/response schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.gateway import (
    ChatCompletionRequest,
    ChatMessage,
    ChatCompletionResponse,
    ChatCompletionChoice,
    TokenUsage,
)


class TestChatCompletionRequest:
    def test_minimal_request(self):
        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="Hello")],
        )
        assert req.model == "gpt-4o"
        assert req.temperature == 1.0  # default
        assert req.max_tokens is None

    def test_full_request(self):
        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[
                ChatMessage(role="system", content="You are a helper."),
                ChatMessage(role="user", content="Hi"),
            ],
            temperature=0.5,
            top_p=0.9,
            max_tokens=1024,
            n=1,
            stop=["\n"],
        )
        assert req.temperature == 0.5
        assert req.max_tokens == 1024

    def test_missing_model_raises(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(
                messages=[ChatMessage(role="user", content="Hi")],
            )

    def test_missing_messages_raises(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(model="gpt-4o")

    def test_empty_messages_raises(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(model="gpt-4o", messages=[])


class TestChatMessage:
    def test_user_message(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_system_message(self):
        msg = ChatMessage(role="system", content="You are helpful.")
        assert msg.role == "system"

    def test_assistant_message(self):
        msg = ChatMessage(role="assistant", content="Hi there!")
        assert msg.role == "assistant"


class TestChatCompletionResponse:
    def test_response_structure(self):
        resp = ChatCompletionResponse(
            id="chatcmpl-123",
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
        assert resp.id == "chatcmpl-123"
        assert resp.choices[0].finish_reason == "stop"
        assert resp.usage.total_tokens == 15

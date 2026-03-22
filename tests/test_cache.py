"""Tests for cache key generation and caching logic."""

import pytest
from app.services.cache import _build_cache_key
from app.schemas.gateway import ChatCompletionRequest, ChatMessage


class TestCacheKeyGeneration:
    def test_same_request_same_key(self):
        """Identical requests must produce the same cache key."""
        req1 = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="hello")],
            temperature=0,
        )
        req2 = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="hello")],
            temperature=0,
        )
        assert _build_cache_key(req1) == _build_cache_key(req2)

    def test_different_model_different_key(self):
        req1 = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="hello")],
        )
        req2 = ChatCompletionRequest(
            model="gpt-4o-mini",
            messages=[ChatMessage(role="user", content="hello")],
        )
        assert _build_cache_key(req1) != _build_cache_key(req2)

    def test_different_message_different_key(self):
        req1 = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="hello")],
        )
        req2 = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="goodbye")],
        )
        assert _build_cache_key(req1) != _build_cache_key(req2)

    def test_different_temperature_different_key(self):
        req1 = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="hello")],
            temperature=0,
        )
        req2 = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="hello")],
            temperature=0.7,
        )
        assert _build_cache_key(req1) != _build_cache_key(req2)

    def test_key_is_sha256_prefixed(self):
        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="test")],
        )
        key = _build_cache_key(req)
        assert key.startswith("cache:chat:")
        assert len(key) == len("cache:chat:") + 64  # SHA256 hex

    def test_multi_message_conversation(self):
        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[
                ChatMessage(role="system", content="You are helpful."),
                ChatMessage(role="user", content="What is 2+2?"),
                ChatMessage(role="assistant", content="4"),
                ChatMessage(role="user", content="And 3+3?"),
            ],
            temperature=0,
        )
        key = _build_cache_key(req)
        assert key.startswith("cache:chat:")

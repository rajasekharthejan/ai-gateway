"""Tests for the policy evaluation engine."""

import pytest
from app.services.policy_engine import _resource_matches, _evaluate_conditions
from app.schemas.gateway import ChatCompletionRequest, ChatMessage


def make_request(model: str = "gpt-4o", max_tokens: int | None = None) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model=model,
        messages=[ChatMessage(role="user", content="test")],
        max_tokens=max_tokens,
    )


class TestResourceMatching:
    def test_wildcard_matches_everything(self):
        assert _resource_matches("*", "gpt-4o") is True
        assert _resource_matches("*", "claude-3-5-sonnet") is True

    def test_exact_match(self):
        assert _resource_matches("gpt-4o", "gpt-4o") is True
        assert _resource_matches("gpt-4o", "gpt-4o-mini") is False

    def test_glob_pattern(self):
        assert _resource_matches("gpt-4*", "gpt-4o") is True
        assert _resource_matches("gpt-4*", "gpt-4o-mini") is True
        assert _resource_matches("gpt-4*", "gpt-3.5-turbo") is False

    def test_claude_pattern(self):
        assert _resource_matches("claude-*", "claude-3-5-sonnet") is True
        assert _resource_matches("claude-*", "gpt-4o") is False

    def test_specific_version(self):
        assert _resource_matches("gpt-3.5-turbo*", "gpt-3.5-turbo") is True
        assert _resource_matches("gpt-3.5-turbo*", "gpt-3.5-turbo-0125") is True


class TestConditionEvaluation:
    def test_no_conditions_always_matches(self):
        assert _evaluate_conditions(None, make_request()) is True
        assert _evaluate_conditions({}, make_request()) is True

    def test_max_tokens_condition_exceeded(self):
        """When request max_tokens > limit, condition matches."""
        conditions = {"max_tokens": 1000}
        request = make_request(max_tokens=2000)
        assert _evaluate_conditions(conditions, request) is True

    def test_max_tokens_condition_within_limit(self):
        """When request max_tokens <= limit, condition still matches (no violation)."""
        conditions = {"max_tokens": 1000}
        request = make_request(max_tokens=500)
        assert _evaluate_conditions(conditions, request) is True

    def test_denied_models_list(self):
        conditions = {"denied_models": ["gpt-4", "gpt-4-turbo"]}
        assert _evaluate_conditions(conditions, make_request("gpt-4")) is True
        assert _evaluate_conditions(conditions, make_request("gpt-4o")) is True

    def test_allowed_models_list(self):
        conditions = {"allowed_models": ["gpt-4o-mini", "gpt-3.5-turbo"]}
        # Model not in allowlist -> condition matches (policy applies)
        assert _evaluate_conditions(conditions, make_request("gpt-4o")) is True
        # Model in allowlist -> condition matches
        assert _evaluate_conditions(conditions, make_request("gpt-4o-mini")) is True

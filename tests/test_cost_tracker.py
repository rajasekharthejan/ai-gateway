"""Tests for cost calculation and pricing."""

import pytest
from app.services.cost_tracker import calculate_cost, _get_pricing, MODEL_PRICING


class TestCalculateCost:
    """Cost calculation tests."""

    def test_gpt4o_mini_cost(self):
        """GPT-4o-mini: 1000 prompt + 500 completion tokens."""
        cost = calculate_cost("gpt-4o-mini", prompt_tokens=1000, completion_tokens=500)
        expected = (1000 * 0.15 / 1_000_000) + (500 * 0.60 / 1_000_000)
        assert abs(cost - expected) < 1e-8

    def test_gpt4o_cost(self):
        """GPT-4o: 1000 prompt + 1000 completion tokens."""
        cost = calculate_cost("gpt-4o", prompt_tokens=1000, completion_tokens=1000)
        expected = (1000 * 2.50 / 1_000_000) + (1000 * 10.00 / 1_000_000)
        assert abs(cost - expected) < 1e-8

    def test_claude_3_5_sonnet_cost(self):
        """Claude 3.5 Sonnet pricing via Bedrock."""
        cost = calculate_cost("claude-3-5-sonnet", prompt_tokens=5000, completion_tokens=2000)
        expected = (5000 * 3.00 / 1_000_000) + (2000 * 15.00 / 1_000_000)
        assert abs(cost - expected) < 1e-8

    def test_zero_tokens(self):
        cost = calculate_cost("gpt-4o", prompt_tokens=0, completion_tokens=0)
        assert cost == 0.0

    def test_large_token_count(self):
        """128K context window scenario."""
        cost = calculate_cost("gpt-4o", prompt_tokens=128000, completion_tokens=4096)
        assert cost > 0
        expected = (128000 * 2.50 / 1_000_000) + (4096 * 10.00 / 1_000_000)
        assert abs(cost - expected) < 1e-6

    def test_prefix_matching(self):
        """Model name with date suffix should match base model pricing."""
        pricing = _get_pricing("gpt-4o-2024-08-06")
        assert pricing == MODEL_PRICING["gpt-4o"]

    def test_unknown_model_uses_default(self):
        """Unknown model should fall back to default pricing."""
        pricing = _get_pricing("unknown-model-v99")
        assert pricing == (10.00, 30.00)

    def test_all_models_have_positive_pricing(self):
        for model, (input_price, output_price) in MODEL_PRICING.items():
            assert input_price > 0, f"{model} has zero/negative input price"
            assert output_price > 0, f"{model} has zero/negative output price"

    def test_output_always_costs_more_than_input(self):
        """For all models, output per-token cost >= input per-token cost."""
        for model, (input_price, output_price) in MODEL_PRICING.items():
            assert output_price >= input_price, (
                f"{model}: output ${output_price} < input ${input_price}"
            )


class TestPricingTable:
    def test_openai_models_present(self):
        for model in ["gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo", "o1", "o3-mini"]:
            assert model in MODEL_PRICING

    def test_claude_models_present(self):
        for model in ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"]:
            assert model in MODEL_PRICING

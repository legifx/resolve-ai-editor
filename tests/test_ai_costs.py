from core.ai.costs import estimate_cost, estimate_tokens, price_for


def test_known_model_price():
    assert price_for("claude-opus-4-8") == (5.00, 25.00)
    assert price_for("gpt-4o-mini") == (0.15, 0.60)


def test_unknown_model_is_none():
    assert price_for("some-random-model") is None
    assert estimate_cost("some-random-model", 1000, 1000) is None


def test_openrouter_free_is_zero():
    assert price_for("meta-llama/llama-3-8b:free") == (0.0, 0.0)
    assert estimate_cost("x:free", 5000, 5000) == 0.0


def test_cost_math():
    # 1M input @ $5 + 1M output @ $25 = $30
    assert estimate_cost("claude-opus-4-8", 1_000_000, 1_000_000) == 30.0
    # 0.5M opus output only
    assert estimate_cost("claude-opus-4-8", 0, 500_000) == 12.5


def test_estimate_tokens_heuristic():
    assert estimate_tokens("") == 1          # floor at 1
    assert estimate_tokens("a" * 400) == 100  # ~4 chars/token

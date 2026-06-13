"""Pricing table + local token/cost estimation.

Prices are USD per 1M tokens (input, output), cached 2026-06 from the
official docs. Unknown models return None — the UI shows "unknown" instead
of a made-up number. Estimates use the ~4 chars/token heuristic and are
labelled as estimates in the UI; exact counts would cost an API round trip.
"""

from typing import Optional, Tuple

# (input $/1M, output $/1M)
PRICES = {
    # Anthropic (platform.claude.com/docs pricing, cached 2026-06)
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    # OpenAI (openai.com/api/pricing, cached 2026-06)
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def price_for(model: str) -> Optional[Tuple[float, float]]:
    if model in PRICES:
        return PRICES[model]
    # OpenRouter free-tier models end in ":free"
    if model.endswith(":free"):
        return (0.0, 0.0)
    return None


def estimate_tokens(text: str) -> int:
    """Rough local estimate (~4 chars/token). Good enough for a UI preview;
    never used for billing decisions."""
    return max(1, len(text) // 4)


def estimate_cost(model: str, input_tokens: int,
                  output_tokens: int) -> Optional[float]:
    price = price_for(model)
    if price is None:
        return None
    return round(
        input_tokens / 1e6 * price[0] + output_tokens / 1e6 * price[1], 6)

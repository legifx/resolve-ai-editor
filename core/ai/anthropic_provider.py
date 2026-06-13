"""Anthropic (Claude) provider — official `anthropic` SDK only.

Install: pip install anthropic   (optional dep; the plugin runs without it,
this provider then reports unavailable with that exact instruction).
"""

from typing import Optional, Tuple

from core.ai.base import AIError, AIProvider, AIResponse
from core.ai.costs import estimate_cost
from core.ai import keys

try:
    import anthropic  # type: ignore
    HAS_SDK = True
except ImportError:
    anthropic = None
    HAS_SDK = False

DEFAULT_MODEL = "claude-opus-4-8"
# Models where adaptive thinking is supported (4.6-family and later Opus).
_ADAPTIVE_MODELS = ("claude-opus-4-8", "claude-opus-4-7",
                    "claude-opus-4-6", "claude-sonnet-4-6")


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def available(self) -> Tuple[bool, str]:
        if not HAS_SDK:
            return False, ("Python package 'anthropic' is not installed. "
                           "Run: pip install anthropic")
        if not keys.get_key("anthropic"):
            return False, "No Anthropic API key stored (Settings > AI Providers)."
        return True, "ok"

    def complete(self, prompt: str, system: Optional[str] = None,
                 max_tokens: int = 1024) -> AIResponse:
        ok, reason = self.available()
        if not ok:
            raise AIError(reason)
        client = anthropic.Anthropic(api_key=keys.get_key("anthropic"))
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        if self.model in _ADAPTIVE_MODELS:
            kwargs["thinking"] = {"type": "adaptive"}
        try:
            resp = client.messages.create(**kwargs)
        except anthropic.AuthenticationError:
            raise AIError("Anthropic: invalid API key.")
        except anthropic.RateLimitError:
            raise AIError("Anthropic: rate limited — try again shortly.")
        except anthropic.APIConnectionError:
            raise AIError("Anthropic: network error — check your connection.")
        except anthropic.APIStatusError as exc:
            raise AIError("Anthropic API error (%s): %s"
                          % (exc.status_code, exc.message))

        text = "".join(b.text for b in resp.content if b.type == "text")
        return AIResponse(
            text=text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            model=self.model,
            provider=self.name,
            cost_usd=estimate_cost(self.model, resp.usage.input_tokens,
                                   resp.usage.output_tokens),
        )

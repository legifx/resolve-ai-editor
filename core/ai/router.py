"""Model routing — cost optimization by task tier (prompt section 4).

Two tiers, user-configurable in Settings:
- "routine":  bulk/simple calls (asset tagging, short labels)
              -> cheapest/free model. Default: OpenRouter (pick a ':free'
                 model there for zero cost).
- "complex":  judgment-heavy calls (cut decisions, genre analysis)
              -> strongest model. Default: Anthropic claude-opus-4-8.

The defaults follow the project requirement (free/cheap first); users with
only one key can point both tiers at the same provider.
"""

from typing import Dict

from core.ai.anthropic_provider import AnthropicProvider, DEFAULT_MODEL
from core.ai.base import AIError, AIProvider
from core.ai.openai_compat import OpenAICompatProvider, DEFAULT_MODELS

TIERS = ("routine", "complex")

DEFAULT_ROUTING = {
    "routine": {"provider": "openrouter",
                "model": DEFAULT_MODELS["openrouter"]},
    "complex": {"provider": "anthropic", "model": DEFAULT_MODEL},
}


def build_provider(provider: str, model: str = "",
                   custom_base_url: str = "") -> AIProvider:
    if provider == "anthropic":
        return AnthropicProvider(model or DEFAULT_MODEL)
    if provider in ("openai", "openrouter"):
        return OpenAICompatProvider(provider, model)
    if provider == "custom":
        return OpenAICompatProvider("custom", model, base_url=custom_base_url)
    raise AIError("Unknown provider '%s'." % provider)


def get_provider_for_tier(tier: str, settings: Dict) -> AIProvider:
    if tier not in TIERS:
        raise AIError("Unknown task tier '%s'." % tier)
    routing = settings.get("ai_routing") or {}
    route = routing.get(tier) or DEFAULT_ROUTING[tier]
    return build_provider(
        route.get("provider", ""), route.get("model", ""),
        settings.get("ai_custom_base_url", ""))

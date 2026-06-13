"""OpenAI-compatible chat-completions provider — covers OpenAI, OpenRouter
and any custom endpoint that speaks the same wire format.

stdlib-only (urllib) so the plugin keeps zero hard dependencies for these
backends. The Anthropic provider deliberately does NOT go through this
shim — it uses the official SDK (see anthropic_provider.py).
"""

import json
import urllib.error
import urllib.request
from typing import Optional, Tuple

from core.ai.base import AIError, AIProvider, AIResponse
from core.ai.costs import estimate_cost
from core.ai import keys

BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    # "custom": base_url comes from settings
}
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "openrouter": "openrouter/auto",  # pick a ':free' model for zero cost
    "custom": "",
}


class OpenAICompatProvider(AIProvider):
    def __init__(self, provider: str, model: str = "",
                 base_url: Optional[str] = None, timeout: int = 120):
        self.name = provider
        self.model = model or DEFAULT_MODELS.get(provider, "")
        self.base_url = (base_url or BASE_URLS.get(provider, "")).rstrip("/")
        self.timeout = timeout

    def available(self) -> Tuple[bool, str]:
        if not self.base_url:
            return False, ("No endpoint URL configured for '%s' "
                           "(Settings > AI Providers)." % self.name)
        if not self.model:
            return False, "No model configured for '%s'." % self.name
        if not keys.get_key(self.name):
            return False, ("No API key stored for '%s' "
                           "(Settings > AI Providers)." % self.name)
        return True, "ok"

    def complete(self, prompt: str, system: Optional[str] = None,
                 max_tokens: int = 1024) -> AIResponse:
        ok, reason = self.available()
        if not ok:
            raise AIError(reason)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }).encode()

        headers = {
            "Authorization": "Bearer %s" % keys.get_key(self.name),
            "Content-Type": "application/json",
        }
        if self.name == "openrouter":  # attribution headers (recommended)
            headers["X-Title"] = "resolve-ai-editor"

        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read().decode()).get(
                    "error", {}).get("message", "")
            except Exception:
                pass
            if exc.code == 401:
                raise AIError("%s: invalid API key." % self.name)
            if exc.code == 429:
                raise AIError("%s: rate limited — try again shortly." % self.name)
            raise AIError("%s API error (%s): %s" % (self.name, exc.code, detail))
        except urllib.error.URLError as exc:
            raise AIError("%s: network error — %s" % (self.name, exc.reason))

        try:
            text = payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise AIError("%s: unexpected response shape." % self.name)
        usage = payload.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)
        return AIResponse(
            text=text, input_tokens=tokens_in, output_tokens=tokens_out,
            model=self.model, provider=self.name,
            cost_usd=estimate_cost(self.model, tokens_in, tokens_out),
        )

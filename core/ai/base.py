"""Provider abstraction — one interface, swappable backends.

Token-optimization contract (prompt section 4): callers send only compact,
pre-processed summaries to `complete()` — never raw media, never full
transcripts. All heavy analysis stays local in core/analyze.
"""

from dataclasses import dataclass
from typing import Optional, Tuple


class AIError(RuntimeError):
    """Provider problem with a user-readable message (no stack traces in UI)."""


@dataclass
class AIResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str
    cost_usd: Optional[float]  # None when pricing for the model is unknown


class AIProvider:
    """Interface every backend implements."""

    name = "base"

    def available(self) -> Tuple[bool, str]:
        """(ok, reason). ok=False must explain what the user has to do."""
        raise NotImplementedError

    def complete(self, prompt: str, system: Optional[str] = None,
                 max_tokens: int = 1024) -> AIResponse:
        raise NotImplementedError

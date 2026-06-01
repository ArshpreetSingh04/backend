"""Pluggable LLM provider abstraction and the responsible-use network guard.

LeadHunter talks to exactly one LLM "box" through one small interface: a
`LLMProvider` with a single `generate()` method (plus a cheap `available()`
probe used for provider selection). Concrete providers are a local **Ollama**
default and a generic **OpenAI-compatible** hosted fallback.

Responsible-use contract (fail closed, mirrors the ingestion sources):
LLM calls perform network I/O — even local Ollama speaks HTTP to localhost.
Construction is side-effect free; ``generate()`` and ``available()`` refuse to
touch the network unless the caller explicitly opts in with
``allow_network=True``, raising `LLMNetworkNotAllowedError` otherwise. Tests
opt in and override the single HTTP seam, so no real calls ever happen.

Stdlib-only: ``abc`` here; ``urllib``/``json``/``os`` in the providers.
"""

from __future__ import annotations

import abc
from typing import Optional


class LLMError(RuntimeError):
    """Base class for all LLM provider errors."""


class LLMNetworkNotAllowedError(LLMError):
    """Raised when an LLM call runs without an explicit network opt-in.

    Responsible-use contract: network access (including localhost Ollama) is
    opt-in only. Providers may only reach the network when constructed (or
    called) with ``allow_network=True``.
    """


class LLMUnavailableError(LLMError):
    """Raised when a provider cannot serve a request (down, or misconfigured)."""


class LLMProvider(abc.ABC):
    """Base class for LLM providers — the single "one prompt / one box" seam.

    Subclasses implement ``generate()`` (and may override ``available()``). The
    ``allow_network`` flag gates the responsible-use opt-in: no network I/O is
    attempted unless it is True. Construction must stay side-effect free so the
    opt-in can fail closed before any I/O.
    """

    #: Human-readable provider name.
    name: str = "llm"

    def __init__(self, *, allow_network: bool = False) -> None:
        # No network here — keep construction side-effect free.
        self.allow_network = allow_network

    def _require_network(self) -> None:
        """Fail closed unless the caller opted into network access."""
        if not self.allow_network:
            raise LLMNetworkNotAllowedError(
                f"LLM provider {self.name!r} requires network access; "
                f"pass allow_network=True to opt in."
            )

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Return the model's text completion for ``prompt``.

        Implementations must call ``self._require_network()`` before any I/O.
        """
        raise NotImplementedError

    def available(self) -> bool:
        """Cheap health probe used for provider selection.

        Default: not available. Network-backed providers override this with a
        gated, mockable check. Must never raise — returns False on any failure.
        """
        return False

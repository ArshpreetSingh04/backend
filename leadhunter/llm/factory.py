"""Provider selection: Ollama default, free hosted fallback.

``get_provider()`` returns a single ready `LLMProvider`. Selection order:

1. An explicit ``prefer`` argument or the ``LLM_PROVIDER`` env var
   ("ollama" | "hosted") forces a specific provider.
2. Otherwise, the locked default: try local **Ollama** (``available()``); if it
   is not running, fall back to the configured **hosted** provider.
3. If neither can serve, raise `LLMUnavailableError` with a clear message.

The opt-in flows through: selection (which may probe Ollama) and the returned
provider only touch the network when ``allow_network=True``.
"""

from __future__ import annotations

import os
from typing import Optional

from .base import LLMProvider, LLMUnavailableError
from .ollama_provider import OllamaProvider
from .hosted_provider import HostedProvider


def get_provider(
    *,
    prefer: Optional[str] = None,
    allow_network: bool = False,
) -> LLMProvider:
    """Return a ready `LLMProvider` per the selection rules above."""
    choice = (prefer or os.environ.get("LLM_PROVIDER") or "").strip().lower()

    if choice == "ollama":
        return OllamaProvider(allow_network=allow_network)
    if choice == "hosted":
        return HostedProvider(allow_network=allow_network)
    if choice:
        raise LLMUnavailableError(f"Unknown LLM provider: {choice!r}")

    # Default: Ollama first (local, free), then hosted fallback.
    ollama = OllamaProvider(allow_network=allow_network)
    if ollama.available():
        return ollama

    hosted = HostedProvider(allow_network=allow_network)
    if hosted.available():
        return hosted

    raise LLMUnavailableError(
        "No LLM provider available: local Ollama is not reachable and no "
        "hosted fallback is configured (set LLM_HOSTED_BASE_URL + "
        "LLM_HOSTED_API_KEY, or start Ollama)."
    )

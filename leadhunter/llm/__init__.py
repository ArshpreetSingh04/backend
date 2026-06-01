"""Pluggable LLM layer for LeadHunter.

One small interface (`LLMProvider.generate`) over one "box". The locked design
is a local **Ollama** default (free) with a generic **OpenAI-compatible** hosted
fallback configured via env — no vendor hard-coded. `get_provider()` picks one.

Responsible-use: every provider is fail-closed; network I/O (including localhost
Ollama) happens only when constructed with ``allow_network=True``. All HTTP goes
through a single seam that tests override, so the suite stays hermetic.
"""

from .base import (
    LLMProvider,
    LLMError,
    LLMNetworkNotAllowedError,
    LLMUnavailableError,
)
from .ollama_provider import OllamaProvider
from .hosted_provider import HostedProvider
from .factory import get_provider

__all__ = [
    "LLMProvider",
    "LLMError",
    "LLMNetworkNotAllowedError",
    "LLMUnavailableError",
    "OllamaProvider",
    "HostedProvider",
    "get_provider",
]

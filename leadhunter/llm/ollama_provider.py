"""Default LLM provider: a local, free Ollama instance.

Ollama exposes a simple HTTP API on ``localhost`` (default port 11434). This is
the locked default because it is local and free. ``generate()`` POSTs to
``/api/generate``; ``available()`` probes ``/api/tags`` so the factory can fall
back when Ollama is not running.

Responsible-use: even though Ollama is local, it is still network I/O, so all
calls are gated by the ``allow_network`` opt-in (fail closed). The single
``_http_post`` seam is the only place that touches the network; tests override
it to return canned fixtures.

Stdlib-only: ``urllib``, ``json``, ``os``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .base import LLMProvider, LLMUnavailableError

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


class OllamaProvider(LLMProvider):
    """Talk to a local Ollama server through its HTTP API."""

    name = "ollama"

    def __init__(
        self,
        *,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
        allow_network: bool = False,
    ) -> None:
        super().__init__(allow_network=allow_network)
        # Env overrides, then sane local defaults. No network at construction.
        self.host = (host or os.environ.get("OLLAMA_HOST") or DEFAULT_HOST).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL") or DEFAULT_MODEL
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> str:
        self._require_network()
        body: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system is not None:
            body["system"] = system
        if max_tokens is not None:
            # Ollama caps generated tokens via options.num_predict.
            body["options"]["num_predict"] = max_tokens

        raw = self._http_post(
            f"{self.host}/api/generate",
            json.dumps(body).encode("utf-8"),
        )
        payload = json.loads(raw)
        return str(payload.get("response", ""))

    def available(self) -> bool:
        """True if the local Ollama server answers ``/api/tags``."""
        if not self.allow_network:
            return False
        try:
            self._http_get(f"{self.host}/api/tags")
            return True
        except Exception:
            return False

    # -- single network seams (overridden in tests for hermeticity) -------

    def _http_post(self, url: str, data: bytes) -> str:
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset)
        except urllib.error.URLError as exc:  # pragma: no cover - real-network path
            raise LLMUnavailableError(f"Ollama request failed: {exc}") from exc

    def _http_get(self, url: str) -> str:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)

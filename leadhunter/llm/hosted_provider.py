"""Free hosted fallback: a generic OpenAI-compatible chat endpoint.

No vendor is hard-coded. The endpoint, model, and API key come from env so any
free OpenAI-compatible tier works (e.g. OpenRouter, Groq, Google AI Studio's
OpenAI-compat shim):

    LLM_HOSTED_BASE_URL   e.g. "https://openrouter.ai/api/v1"
    LLM_HOSTED_MODEL      e.g. "meta-llama/llama-3.2-3b-instruct:free"
    LLM_HOSTED_API_KEY    bearer token for the chosen free tier

``generate()`` POSTs to ``{base_url}/chat/completions`` and returns
``choices[0].message.content``. ``available()`` is True only when a base URL and
key are configured (no network probe needed — it is the fallback).

Responsible-use: gated by the ``allow_network`` opt-in (fail closed). The single
``_http_post`` seam is the only network touchpoint; tests override it.

Stdlib-only: ``urllib``, ``json``, ``os``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .base import LLMProvider, LLMUnavailableError


class HostedProvider(LLMProvider):
    """Call a generic OpenAI-compatible ``/chat/completions`` endpoint."""

    name = "hosted"

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        allow_network: bool = False,
    ) -> None:
        super().__init__(allow_network=allow_network)
        # Env-driven config; no network at construction.
        base = base_url or os.environ.get("LLM_HOSTED_BASE_URL") or ""
        self.base_url = base.rstrip("/")
        self.model = model or os.environ.get("LLM_HOSTED_MODEL") or ""
        self.api_key = api_key or os.environ.get("LLM_HOSTED_API_KEY") or ""
        self.timeout = timeout

    def available(self) -> bool:
        """True when a base URL and API key are configured (no network probe)."""
        return bool(self.base_url and self.api_key)

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> str:
        self._require_network()
        if not self.base_url or not self.api_key:
            raise LLMUnavailableError(
                "Hosted provider needs LLM_HOSTED_BASE_URL and LLM_HOSTED_API_KEY."
            )

        messages: List[Dict[str, str]] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        raw = self._http_post(
            f"{self.base_url}/chat/completions",
            json.dumps(body).encode("utf-8"),
        )
        payload = json.loads(raw)
        choices = payload.get("choices") or []
        if not choices:
            return ""
        return str(choices[0].get("message", {}).get("content", ""))

    # -- single network seam (overridden in tests for hermeticity) --------

    def _http_post(self, url: str, data: bytes) -> str:
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset)
        except urllib.error.URLError as exc:  # pragma: no cover - real-network path
            raise LLMUnavailableError(f"Hosted request failed: {exc}") from exc

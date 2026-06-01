"""Optional LLM booster scorer — fail-closed, behind the `Enricher` contract.

`LLMScorer` wraps a deterministic ``baseline`` and an optional `LLMProvider`.
It can only ever *improve* on an already-valid baseline score: if the network
opt-in is off, no provider is configured, the provider is unavailable, or the
model reply cannot be parsed, it returns ``baseline.score(lead)`` unchanged.

Responsible-use: like the ingestion sources and LLM providers, network access
is opt-in. The provider's own ``allow_network`` flag governs whether
``generate()`` may touch the network; here we additionally short-circuit to the
baseline unless ``allow_network=True`` so no provider method is even called.

Stdlib-only (``json``). Tests inject a fake provider, so no real LLM is used.
"""

from __future__ import annotations

import json
from typing import Optional

from ..ingestion.model import Lead
from ..llm.base import LLMError, LLMProvider
from .base import Enricher, Score


_SYSTEM = (
    "You are a B2B sales lead qualifier. Given a lead's fields, rate how "
    "promising it is from 0 to 100 and give brief reasons. Respond with ONLY "
    "a JSON object: {\"score\": <int 0-100>, \"reasons\": [<short strings>]}."
)


def _build_prompt(lead: Lead) -> str:
    """Render the lead's identity fields into a compact prompt."""
    fields = {
        "name": lead.name,
        "company": lead.company,
        "email": lead.email,
        "domain": lead.domain,
        "phone": lead.phone,
        "source": lead.source,
    }
    lines = [f"{k}: {v}" for k, v in fields.items() if v]
    body = "\n".join(lines) if lines else "(no identifying fields)"
    return f"Lead:\n{body}\n\nReturn the JSON object now."


def _parse_reply(text: str):
    """Parse the model reply into (score:int, reasons:list[str]).

    Tolerant of surrounding prose: extracts the first ``{...}`` block. Raises
    ValueError on anything unparseable so the caller can fall back.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in reply")
    obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict) or "score" not in obj:
        raise ValueError("reply missing 'score'")
    score = int(obj["score"])
    raw_reasons = obj.get("reasons") or []
    if isinstance(raw_reasons, str):
        raw_reasons = [raw_reasons]
    reasons = [str(r) for r in raw_reasons]
    return score, reasons


class LLMScorer(Enricher):
    """LLM-backed scorer that degrades gracefully to a deterministic baseline."""

    def __init__(
        self,
        baseline: Enricher,
        provider: Optional[LLMProvider] = None,
        *,
        allow_network: bool = False,
    ) -> None:
        self.baseline = baseline
        self.provider = provider
        self.allow_network = allow_network
        self.name = f"llm:{provider.name}" if provider is not None else "llm"

    def _can_use_llm(self) -> bool:
        """Only attempt the LLM when explicitly allowed and reachable."""
        if not self.allow_network or self.provider is None:
            return False
        try:
            return bool(self.provider.available())
        except Exception:
            # available() should never raise, but stay fail-closed regardless.
            return False

    def score(self, lead: Lead) -> Score:
        if not self._can_use_llm():
            return self.baseline.score(lead)
        try:
            reply = self.provider.generate(
                _build_prompt(lead),
                system=_SYSTEM,
                temperature=0.0,
            )
            value, reasons = _parse_reply(reply)
        except (LLMError, ValueError, TypeError, KeyError):
            # Any model/transport/parse failure -> deterministic floor.
            return self.baseline.score(lead)
        if not reasons:
            reasons = ["llm assessment"]
        return Score.make(value, reasons, self.name)

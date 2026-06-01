"""Optional LLM booster planner — fail-closed, behind the `PlanBuilder` contract.

`LLMPlanBuilder` wraps a deterministic ``baseline`` and an optional `LLMProvider`.
It can only ever *refine* an already-valid baseline plan: if the network opt-in
is off, no provider is configured, the provider is unavailable, or the model
reply cannot be parsed, it returns ``baseline.build(prompt)`` unchanged. Any
fields the model omits fall back to the baseline's values (a merge, never a
regression), so callers always get a complete `SearchPlan`.

Responsible-use: like the ingestion sources and LLM providers, network access is
opt-in. We short-circuit to the baseline unless ``allow_network=True`` so no
provider method is even called.

Stdlib-only (``json``). Tests inject a fake provider, so no real LLM is used.
"""

from __future__ import annotations

import json
from typing import Optional

from ..llm.base import LLMError, LLMProvider
from .base import PlanBuilder, SearchPlan
from .rules import RulePlanBuilder

_SYSTEM = (
    "You convert a sales user's request into a lead-search plan. Respond with "
    "ONLY a JSON object: {\"vertical\": <business type, singular>, "
    "\"location\": <where>, \"required_fields\": [<any of email, phone, "
    "website>], \"target_count\": <int>}."
)


def _build_prompt(prompt: str) -> str:
    """Render the user's request for the model."""
    return f'User request:\n"{prompt}"\n\nReturn the JSON object now.'


def _parse_reply(text: str) -> dict:
    """Extract the first ``{...}`` JSON object from the reply.

    Tolerant of surrounding prose. Raises ValueError on anything unparseable so
    the caller can fall back to the baseline plan.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in reply")
    obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("reply is not a JSON object")
    return obj


class LLMPlanBuilder(PlanBuilder):
    """LLM-backed planner that degrades gracefully to a deterministic baseline."""

    def __init__(
        self,
        baseline: PlanBuilder,
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

    def build(self, prompt: str) -> SearchPlan:
        base = self.baseline.build(prompt)
        if not self._can_use_llm():
            return base
        try:
            reply = self.provider.generate(
                _build_prompt(prompt),
                system=_SYSTEM,
                temperature=0.0,
            )
            obj = _parse_reply(reply)
        except (LLMError, ValueError, TypeError, KeyError):
            # Any model/transport/parse failure -> deterministic baseline.
            return base
        # Merge: the model refines the baseline; omitted fields keep baseline values.
        vertical = obj.get("vertical") or base.vertical
        location = obj.get("location") or base.location
        fields = obj.get("required_fields")
        if not isinstance(fields, (list, tuple)) or not fields:
            fields = base.required_fields
        count = obj.get("target_count", base.target_count)
        return SearchPlan.make(
            vertical=str(vertical),
            location=str(location),
            required_fields=[str(f) for f in fields],
            target_count=count,
            raw_prompt=prompt or "",
            method=self.name,
        )


def build_plan(
    prompt: str,
    *,
    allow_network: bool = False,
    provider: Optional[LLMProvider] = None,
) -> SearchPlan:
    """Convenience front door: parse ``prompt`` into a `SearchPlan`.

    Uses the deterministic `RulePlanBuilder` as the floor and, when allowed and a
    reachable provider is supplied, lets `LLMPlanBuilder` refine it (fail-closed).
    """
    baseline = RulePlanBuilder()
    if provider is None and not allow_network:
        return baseline.build(prompt)
    builder = LLMPlanBuilder(baseline, provider, allow_network=allow_network)
    return builder.build(prompt)

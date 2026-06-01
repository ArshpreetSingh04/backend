"""Planning contract: the `PlanBuilder` seam and the `SearchPlan` result.

M3 (Planning & Discovery) begins the locked objective's front door: a single
natural-language prompt (the one "Find Leads" box) becomes a structured,
machine-readable `SearchPlan` that downstream discovery/browsing can consume.

Every builder implements the same small `PlanBuilder` interface so the
deterministic baseline and the optional LLM booster are interchangeable, exactly
like the M2 scoring `Enricher`/`RuleScorer`/`LLMScorer` trio.

Stdlib-only (``abc``, ``dataclasses``).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Iterable, Tuple

#: Default number of leads to target when the prompt names no count.
DEFAULT_TARGET_COUNT = 25

#: Canonical ordering for the contact fields a plan may require.
CANONICAL_FIELDS = ("email", "phone", "website")


class PlanError(RuntimeError):
    """Base class for planning errors."""


def normalize_fields(fields: Iterable[str]) -> Tuple[str, ...]:
    """Lower/strip requested fields, drop blanks/dupes, keep canonical order."""
    seen = {f.strip().casefold() for f in fields if f and f.strip()}
    ordered = [f for f in CANONICAL_FIELDS if f in seen]
    # Preserve any non-canonical extras (deterministically, after the known ones).
    extras = sorted(seen - set(CANONICAL_FIELDS))
    return tuple(ordered + extras)


@dataclass(frozen=True)
class SearchPlan:
    """A structured search intent parsed from a one-box prompt.

    `vertical` is the business type to find, `location` is where, `required_fields`
    are the contact fields a lead must carry to count, `target_count` is how many
    leads to gather, `raw_prompt` is the verbatim user input, and `method` records
    who produced the plan ("rules" or "llm:<provider>"). Immutable so it can be
    safely passed down the pipeline.
    """

    vertical: str
    location: str
    required_fields: Tuple[str, ...]
    target_count: int
    raw_prompt: str
    method: str

    @classmethod
    def make(
        cls,
        *,
        vertical: str,
        location: str,
        required_fields: Iterable[str],
        target_count: int,
        raw_prompt: str,
        method: str,
    ) -> "SearchPlan":
        """Build a `SearchPlan`, normalizing fields and flooring the count at 1."""
        try:
            count = int(target_count)
        except (TypeError, ValueError):
            count = DEFAULT_TARGET_COUNT
        return cls(
            vertical=(vertical or "").strip(),
            location=(location or "").strip(),
            required_fields=normalize_fields(required_fields),
            target_count=max(1, count),
            raw_prompt=raw_prompt or "",
            method=method,
        )


class PlanBuilder(abc.ABC):
    """The single planning seam: take a prompt string, return a `SearchPlan`.

    Implementations must be safe to call without network access. The optional
    LLM booster honors the responsible-use opt-in and falls back to a
    deterministic baseline, so callers always get a valid `SearchPlan`.
    """

    #: Human-readable builder name.
    name: str = "plan_builder"

    @abc.abstractmethod
    def build(self, prompt: str) -> SearchPlan:
        """Return a `SearchPlan` for ``prompt``. Must never require the network."""
        raise NotImplementedError

"""Scoring contract: the single `Enricher` seam and the `Score` result.

M2 (Enrichment & Scoring) turns a persisted `Lead` into a qualification
`Score`. Every scorer implements the same small `Enricher` interface so the
deterministic baseline and the optional LLM booster are interchangeable.

Stdlib-only (``abc``, ``dataclasses``).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Tuple

from ..ingestion.model import Lead


# Tier thresholds on the clamped 0..100 score.
TIER_WARM_MIN = 34
TIER_HOT_MIN = 67


def clamp_score(value: int) -> int:
    """Clamp an arbitrary integer into the inclusive 0..100 range."""
    return max(0, min(100, int(value)))


def tier_for(value: int) -> str:
    """Map a clamped score to a coarse qualification tier."""
    if value >= TIER_HOT_MIN:
        return "hot"
    if value >= TIER_WARM_MIN:
        return "warm"
    return "cold"


@dataclass(frozen=True)
class Score:
    """A qualification score for one lead.

    `value` is clamped 0..100, `tier` is derived from it, `reasons` explains
    the contributions, and `method` records who produced it ("rules" or
    "llm:<provider>"). Immutable so it can be safely passed around and cached.
    """

    value: int
    tier: str
    reasons: Tuple[str, ...]
    method: str

    @classmethod
    def make(cls, value: int, reasons, method: str) -> "Score":
        """Build a `Score`, clamping the value and deriving the tier."""
        clamped = clamp_score(value)
        return cls(
            value=clamped,
            tier=tier_for(clamped),
            reasons=tuple(reasons),
            method=method,
        )


class Enricher(abc.ABC):
    """The single scoring seam: take a `Lead`, return a `Score`.

    Implementations must be safe to call without network access. The optional
    LLM booster honors the responsible-use opt-in and falls back to a
    deterministic baseline, so callers always get a valid `Score`.
    """

    #: Human-readable scorer name.
    name: str = "enricher"

    @abc.abstractmethod
    def score(self, lead: Lead) -> Score:
        """Return a `Score` for ``lead``. Must never require the network."""
        raise NotImplementedError

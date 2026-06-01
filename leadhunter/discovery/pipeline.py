"""Discovery orchestration: plan -> ranked, de-duplicated candidate sources.

`discover_sources()` is the single driver: it runs one or more
`SourceDiscoverer`s over a `SearchPlan`, merges and de-duplicates their
candidates by ``(kind, query)``, re-ranks the union, and returns it together
with a `DiscoverySummary`.

Responsible-use opt-in: a discoverer that declares ``requires_network = True``
is refused with `DiscoveryNetworkNotAllowedError` unless ``allow_network=True``
is passed, mirroring the ingestion and enrichment pipeline guards. The default
`RuleSourceDiscoverer` is offline, so the gate is the seam for any future
network-backed discoverer.

Stdlib-only; performs no network I/O of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..planning.base import SearchPlan
from .base import (
    CandidateSource,
    DiscoveryNetworkNotAllowedError,
    SourceDiscoverer,
    rank_candidates,
)
from .rules import RuleSourceDiscoverer


@dataclass
class DiscoverySummary:
    """Aggregate outcome of a `discover_sources()` run."""

    total: int = 0                                       # candidates returned
    by_kind: Dict[str, int] = field(default_factory=dict)  # kind -> count


def discover_sources(
    plan: SearchPlan,
    discoverers: Optional[Sequence[SourceDiscoverer]] = None,
    *,
    allow_network: bool = False,
) -> Tuple[DiscoverySummary, List[CandidateSource]]:
    """Discover ranked candidate sources for ``plan``.

    Defaults to the deterministic, offline `RuleSourceDiscoverer`. Candidates
    from all discoverers are merged, de-duplicated by ``(kind, query)`` (first
    occurrence wins), and re-ranked. Deterministic given deterministic
    discoverers; performs no network I/O itself.

    Raises `DiscoveryNetworkNotAllowedError` if any discoverer requires network
    access and ``allow_network`` is not set.
    """
    if discoverers is None:
        discoverers = [RuleSourceDiscoverer()]

    for discoverer in discoverers:
        if getattr(discoverer, "requires_network", False) and not allow_network:
            raise DiscoveryNetworkNotAllowedError(
                f"Discoverer {getattr(discoverer, 'name', discoverer)!r} requires "
                f"network access; pass allow_network=True to opt in."
            )

    seen: set = set()
    merged: List[CandidateSource] = []
    for discoverer in discoverers:
        for candidate in discoverer.discover(plan):
            key = (candidate.kind, candidate.query)
            if key in seen:
                continue
            seen.add(key)
            merged.append(candidate)

    ranked = rank_candidates(merged)

    summary = DiscoverySummary(total=len(ranked))
    for candidate in ranked:
        summary.by_kind[candidate.kind] = summary.by_kind.get(candidate.kind, 0) + 1
    return summary, ranked

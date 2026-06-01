"""Enrichment orchestration: read leads -> enrich -> return results + summary.

`enrich_all()` is the single driver: it reads leads from a `LeadStore`, runs an
`IdentityEnricher` over each, and returns BOTH the per-lead `EnrichResult`s (a
usable in-memory artifact, and a clean handoff for the future persistence
increment) and an `EnrichSummary` of what changed.

This slice is intentionally read-only with respect to the store: it does not
write enriched leads back. Persisting them (via upsert + a dual-sink
``EnrichmentStore``) is the next planned increment.

Responsible-use opt-in: an enricher that declares ``requires_network = True`` is
refused with `EnrichmentNetworkNotAllowedError` unless ``allow_network=True`` is
passed, mirroring the ingestion pipeline's guard. Stdlib-only; no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ..ingestion.persistence import LeadStore
from .base import EnrichmentNetworkNotAllowedError, EnrichResult, IdentityEnricher


@dataclass
class EnrichSummary:
    """Aggregate outcome of an `enrich_all()` run."""

    processed: int = 0                                  # leads read and enriched
    changed: int = 0                                    # leads that gained a field
    filled_by_field: Dict[str, int] = field(default_factory=dict)  # field -> count


def enrich_all(
    lead_store: LeadStore,
    enricher: IdentityEnricher,
    *,
    allow_network: bool = False,
) -> Tuple[EnrichSummary, List[EnrichResult]]:
    """Enrich every lead in ``lead_store`` with ``enricher``.

    Returns ``(summary, results)``. ``results`` holds one `EnrichResult` per
    lead in store order; the store itself is left unmodified. Deterministic
    given a deterministic enricher; performs no network I/O of its own.

    Raises `EnrichmentNetworkNotAllowedError` if ``enricher`` requires network
    access and ``allow_network`` is not set.
    """
    if getattr(enricher, "requires_network", False) and not allow_network:
        raise EnrichmentNetworkNotAllowedError(
            f"Enricher {getattr(enricher, 'name', enricher)!r} requires network "
            f"access; pass allow_network=True to opt in."
        )

    summary = EnrichSummary()
    results: List[EnrichResult] = []
    for lead in lead_store.all():
        result = enricher.enrich(lead)
        results.append(result)
        summary.processed += 1
        if result.changed:
            summary.changed += 1
            for fname in result.filled:
                summary.filled_by_field[fname] = (
                    summary.filled_by_field.get(fname, 0) + 1
                )
    return summary, results

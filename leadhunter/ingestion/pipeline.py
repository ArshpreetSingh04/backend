"""Ingestion orchestration: source -> normalize -> dedup -> persist.

`ingest()` is the single seam that pulls raw records from one or more sources,
normalizes them into `Lead`s, collapses duplicates within the batch, and writes
them idempotently to a `LeadStore` (SQLite truth + CSV mirror).

Responsible-use opt-in: a source that declares ``requires_network = True`` is
refused with `NetworkNotAllowedError` unless ``allow_network=True`` is passed,
so later scrapers cannot reach the network by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .normalize import normalize_lead, dedup
from .persistence import LeadStore
from .model import Lead
from .sources.base import Source, NetworkNotAllowedError


@dataclass
class IngestResult:
    """Outcome of an `ingest()` run."""

    read: int = 0          # raw records pulled from all sources
    after_dedup: int = 0   # leads remaining after in-batch dedup
    inserted: int = 0      # rows newly inserted into SQLite (excludes existing)


def ingest(
    sources: Iterable[Source],
    store: LeadStore,
    *,
    allow_network: bool = False,
) -> IngestResult:
    """Ingest raw records from `sources` into `store`.

    Enforces the network opt-in per source, normalizes each raw record, dedups
    the combined batch, then persists idempotently. Returns counts.
    """
    leads: List[Lead] = []
    read = 0
    for source in sources:
        if getattr(source, "requires_network", False) and not allow_network:
            raise NetworkNotAllowedError(
                f"Source {getattr(source, 'name', source)!r} requires network "
                f"access; pass allow_network=True to opt in."
            )
        for raw in source.records():
            read += 1
            leads.append(normalize_lead(raw))

    deduped = dedup(leads)
    inserted = store.add(deduped)
    return IngestResult(read=read, after_dedup=len(deduped), inserted=inserted)

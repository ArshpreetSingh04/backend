"""The consolidated, actionable output record: one `QualifiedLead`.

M2's final slice *feeds scores/enrichment back into the ingestion output*: it
joins the three dual-sink stores — ingestion `leads` (identity truth),
`enriched_leads` (filled identity), and `lead_scores` (qualification) — into a
single flat record per lead. `QualifiedLead` carries the **best-known identity**
(enriched value preferred, original as fallback), the qualification
score/tier/reasons, and light provenance (which enricher/scorer produced the
values) so the row is self-explaining for a human or a downstream export.

Stdlib-only (``dataclasses``, ``json``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple


@dataclass(frozen=True)
class QualifiedLead:
    """A lead joined across ingestion + enrichment + scoring.

    Identity fields hold the best-known value (enriched preferred over the
    original ingested value). `score`/`tier`/`reasons`/`score_method` come from
    the scoring store (defaults mean "not scored yet"). `enrichment_method` and
    `filled` record what enrichment, if any, contributed. Immutable so it can be
    safely passed to a persistence/export step.
    """

    # --- identity (best-known) ---
    dedup_key: str = ""
    name: str = ""
    company: str = ""
    email: str = ""
    domain: str = ""
    phone: str = ""
    source: str = ""
    source_url: str = ""
    first_seen_at: str = ""
    # --- qualification (from scoring) ---
    score: int = 0
    tier: str = ""
    reasons: Tuple[str, ...] = ()
    score_method: str = ""
    # --- provenance (from enrichment) ---
    enrichment_method: str = ""
    filled: Tuple[str, ...] = ()

    # Column order shared by SQLite and the derived CSV mirror.
    COLUMNS = (
        "dedup_key",
        "name",
        "company",
        "email",
        "domain",
        "phone",
        "source",
        "source_url",
        "first_seen_at",
        "score",
        "tier",
        "reasons",
        "score_method",
        "enrichment_method",
        "filled",
    )

    @property
    def scored(self) -> bool:
        """True when a scorer produced this row's score."""
        return bool(self.score_method)

    @property
    def enriched(self) -> bool:
        """True when an enricher filled at least one field for this lead."""
        return bool(self.filled)

    def to_row(self) -> dict:
        """Serialize to a flat row dict (tuples -> JSON strings)."""
        return {
            "dedup_key": self.dedup_key,
            "name": self.name,
            "company": self.company,
            "email": self.email,
            "domain": self.domain,
            "phone": self.phone,
            "source": self.source,
            "source_url": self.source_url,
            "first_seen_at": self.first_seen_at,
            "score": int(self.score),
            "tier": self.tier,
            "reasons": json.dumps(list(self.reasons), ensure_ascii=False),
            "score_method": self.score_method,
            "enrichment_method": self.enrichment_method,
            "filled": json.dumps(list(self.filled), ensure_ascii=False),
        }

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "QualifiedLead":
        """Rebuild a `QualifiedLead` from a flat row dict (JSON strings -> tuples)."""
        return cls(
            dedup_key=row.get("dedup_key", "") or "",
            name=row.get("name", "") or "",
            company=row.get("company", "") or "",
            email=row.get("email", "") or "",
            domain=row.get("domain", "") or "",
            phone=row.get("phone", "") or "",
            source=row.get("source", "") or "",
            source_url=row.get("source_url", "") or "",
            first_seen_at=row.get("first_seen_at", "") or "",
            score=int(row.get("score") or 0),
            tier=row.get("tier", "") or "",
            reasons=tuple(_load_list(row.get("reasons"))),
            score_method=row.get("score_method", "") or "",
            enrichment_method=row.get("enrichment_method", "") or "",
            filled=tuple(_load_list(row.get("filled"))),
        )


def _load_list(value: Any) -> list:
    """Decode a JSON-list column tolerant of empties and already-decoded lists."""
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return json.loads(value)

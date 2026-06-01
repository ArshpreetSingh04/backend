"""Join ingestion + enrichment + scoring into `QualifiedLead` records.

`assemble_qualified()` is read-only across all three stores: it reads the
ingested `leads` as the lead universe and *left-joins* the enriched identity and
the qualification score by ``dedup_key``. Missing enrichment/scoring simply means
those columns fall back to the ingested value / "not scored". The result is
sorted by score descending (then ``dedup_key``) so the most actionable leads
surface first — the same ordering convention as `ScoreStore.all()`.

Stdlib-only; no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..ingestion.model import Lead
from ..ingestion.persistence import LeadStore
from .base import QualifiedLead, _load_list

# Identity fields where an enriched value, when present, is preferred over the
# original ingested value. (dedup_key/first_seen_at come from the base lead.)
_IDENTITY_FIELDS = ("name", "company", "email", "domain", "phone", "source", "source_url")


@dataclass
class QualifiedSummary:
    """Aggregate outcome of an `assemble_qualified()` / output build."""

    total: int = 0                                          # leads in the output
    scored: int = 0                                         # leads with a score
    enriched: int = 0                                       # leads with filled fields
    by_tier: Dict[str, int] = field(default_factory=dict)  # tier -> count


def _best_identity(base: Lead, enriched: Optional[Lead]) -> Dict[str, str]:
    """Per-field best-known identity: enriched non-empty wins, else the base value."""
    out: Dict[str, str] = {}
    for f in _IDENTITY_FIELDS:
        base_val = (getattr(base, f, "") or "").strip()
        enr_val = (getattr(enriched, f, "") or "").strip() if enriched else ""
        out[f] = enr_val or base_val
    return out


def assemble_qualified(
    lead_store: LeadStore,
    *,
    enrichment_store=None,
    score_store=None,
) -> Tuple[QualifiedSummary, List[QualifiedLead]]:
    """Join ingested leads with their enrichment + score into `QualifiedLead`s.

    Returns ``(summary, qualified)``. ``enrichment_store`` / ``score_store`` are
    optional: when omitted (or with no matching row), the output falls back to
    the ingested identity and an unscored row. Deterministic; performs no I/O of
    its own beyond reading the supplied stores. Sorted by score desc, dedup_key.
    """
    # key -> enriched Lead (the snapshot already merges original + filled fields).
    enrich_map: Dict[str, Tuple[Lead, dict]] = {}
    if enrichment_store is not None:
        enrich_map = {lead.dedup_key: (lead, meta) for lead, meta in enrichment_store.all()}

    # key -> score row dict.
    score_map: Dict[str, dict] = {}
    if score_store is not None:
        score_map = {row["dedup_key"]: row for row in score_store.all()}

    qualified: List[QualifiedLead] = []
    for base in lead_store.all():
        key = base.dedup_key
        enr_lead, enr_meta = enrich_map.get(key, (None, None))
        identity = _best_identity(base, enr_lead)

        score_row = score_map.get(key)
        if score_row is not None:
            score_val = int(score_row.get("score") or 0)
            tier = score_row.get("tier", "") or ""
            reasons = tuple(_load_list(score_row.get("reasons")))
            score_method = score_row.get("method", "") or ""
        else:
            score_val, tier, reasons, score_method = 0, "", (), ""

        enrichment_method = (enr_meta or {}).get("method", "") if enr_meta else ""
        filled = tuple((enr_meta or {}).get("filled", []) or ()) if enr_meta else ()

        qualified.append(
            QualifiedLead(
                dedup_key=key,
                first_seen_at=base.first_seen_at,
                score=score_val,
                tier=tier,
                reasons=reasons,
                score_method=score_method,
                enrichment_method=enrichment_method,
                filled=filled,
                **identity,
            )
        )

    # Most actionable first: highest score, then a stable key tiebreak.
    qualified.sort(key=lambda q: (-q.score, q.dedup_key))

    summary = QualifiedSummary(total=len(qualified))
    for q in qualified:
        if q.scored:
            summary.scored += 1
        if q.enriched:
            summary.enriched += 1
        if q.tier:
            summary.by_tier[q.tier] = summary.by_tier.get(q.tier, 0) + 1
    return summary, qualified

"""LeadHunter enrichment package: fill missing identity fields behind one seam.

Public API:
- `IdentityEnricher` — the enrichment contract (fills fields; distinct from
  scoring's `Enricher`, which returns a `Score`).
- `EnrichResult` / `EnrichmentNetworkNotAllowedError` — result + opt-in guard.
- `DerivationEnricher` — deterministic, no-network default enricher.
- `WebContactEnricher` / `RobotsDisallowedError` — opt-in network enricher that
  fills email/phone from the lead's own published website (fail-closed).
- `enrich_all` / `EnrichSummary` — the driver and its aggregate outcome.
- `EnrichmentStore` — dual-sink persistence (SQLite truth + derived CSV mirror).
- `persist_enrichments` / `enrich_and_persist` — write/convenience drivers.
"""

from .base import (
    EnrichmentNetworkNotAllowedError,
    EnrichResult,
    IdentityEnricher,
)
from .derive import DerivationEnricher
from .enrichment_store import (
    EnrichmentStore,
    enrich_and_persist,
    persist_enrichments,
)
from .pipeline import EnrichSummary, enrich_all
from .web_contact import RobotsDisallowedError, WebContactEnricher

__all__ = [
    "IdentityEnricher",
    "EnrichResult",
    "EnrichmentNetworkNotAllowedError",
    "DerivationEnricher",
    "WebContactEnricher",
    "RobotsDisallowedError",
    "enrich_all",
    "EnrichSummary",
    "EnrichmentStore",
    "persist_enrichments",
    "enrich_and_persist",
]

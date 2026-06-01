"""LeadHunter enrichment package: fill missing identity fields behind one seam.

Public API:
- `IdentityEnricher` — the enrichment contract (fills fields; distinct from
  scoring's `Enricher`, which returns a `Score`).
- `EnrichResult` / `EnrichmentNetworkNotAllowedError` — result + opt-in guard.
- `DerivationEnricher` — deterministic, no-network default enricher.
- `enrich_all` / `EnrichSummary` — the driver and its aggregate outcome.
"""

from .base import (
    EnrichmentNetworkNotAllowedError,
    EnrichResult,
    IdentityEnricher,
)
from .derive import DerivationEnricher
from .pipeline import EnrichSummary, enrich_all

__all__ = [
    "IdentityEnricher",
    "EnrichResult",
    "EnrichmentNetworkNotAllowedError",
    "DerivationEnricher",
    "enrich_all",
    "EnrichSummary",
]

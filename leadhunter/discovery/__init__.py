"""LeadHunter discovery (M3): `SearchPlan` -> ranked candidate sources.

Public surface:
- `CandidateSource`, `SourceDiscoverer` — the discovery contract.
- `RuleSourceDiscoverer` — deterministic, no-network baseline (the floor).
- `discover_sources` / `DiscoverySummary` — the driver and its aggregate outcome.
- `rank_candidates`, `preference_score` — deterministic ranking helpers.
- `DiscoveryError`, `DiscoveryNetworkNotAllowedError` — errors / opt-in guard.
- Kind/risk constants: `OFFICIAL_API`, `STRUCTURED_DIRECTORY`, `WEB_SEARCH`,
  `KINDS`, `RISK_LEVELS`.
"""

from .base import (
    KINDS,
    OFFICIAL_API,
    RISK_LEVELS,
    STRUCTURED_DIRECTORY,
    WEB_SEARCH,
    CandidateSource,
    DiscoveryError,
    DiscoveryNetworkNotAllowedError,
    SourceDiscoverer,
    preference_score,
    rank_candidates,
)
from .pipeline import DiscoverySummary, discover_sources
from .rules import RuleSourceDiscoverer

__all__ = [
    "CandidateSource",
    "SourceDiscoverer",
    "RuleSourceDiscoverer",
    "discover_sources",
    "DiscoverySummary",
    "rank_candidates",
    "preference_score",
    "DiscoveryError",
    "DiscoveryNetworkNotAllowedError",
    "OFFICIAL_API",
    "STRUCTURED_DIRECTORY",
    "WEB_SEARCH",
    "KINDS",
    "RISK_LEVELS",
]

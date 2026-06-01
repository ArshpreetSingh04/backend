"""Discovery contract: the `SourceDiscoverer` seam and `CandidateSource` result.

M3 Increment 2 turns a structured `SearchPlan` (the one-box prompt's parsed
intent) into a ranked list of **candidate sources** — descriptors of *where* to
look for leads. Discovery only *describes* candidates; it never fetches them.
The actual browsing/fetching (and its robots.txt/rate-limit/ToS handling) lives
in the ingestion network layer and is gated by the existing opt-in.

Every discoverer implements the same small `SourceDiscoverer` interface so a
deterministic baseline and any future network-backed discoverer are
interchangeable, exactly like the M2 scoring `Enricher` trio and the M3
planning `PlanBuilder` pair.

Responsible-use posture, encoded in the data:
- Each `CandidateSource` carries a ``kind`` (official_api > structured_directory
  > web_search, by preference) and a ``risk`` flag so risky/freeform scraping
  sorts last and can be isolated downstream.
- ``requires_network`` on a *candidate* is descriptive metadata: acting on it
  later will touch the network. ``requires_network`` on a *discoverer* is the
  fail-closed opt-in gate enforced by `discovery.pipeline.discover_sources`.

Stdlib-only (``abc``, ``dataclasses``, ``json``).
"""

from __future__ import annotations

import abc
import json
from dataclasses import dataclass, replace
from typing import Any, Iterable, List, Mapping

# --- candidate kinds, ordered most-preferred (official) -> least (freeform) ---
OFFICIAL_API = "official_api"
STRUCTURED_DIRECTORY = "structured_directory"
WEB_SEARCH = "web_search"
KINDS = (OFFICIAL_API, STRUCTURED_DIRECTORY, WEB_SEARCH)

# --- risk levels for responsible-use isolation ---
RISK_LEVELS = ("low", "medium", "high")

# Preference weights: higher = surfaced first. Official/structured beat freeform;
# higher risk is penalized so the safe, compliant sources rank ahead.
KIND_WEIGHT = {OFFICIAL_API: 100.0, STRUCTURED_DIRECTORY: 60.0, WEB_SEARCH: 30.0}
RISK_PENALTY = {"low": 0.0, "medium": 5.0, "high": 10.0}


class DiscoveryError(RuntimeError):
    """Base class for discovery errors."""


class DiscoveryNetworkNotAllowedError(DiscoveryError):
    """Raised when a network-requiring discoverer runs without an explicit opt-in.

    Responsible-use contract: a `SourceDiscoverer` that sets
    ``requires_network = True`` may only run when `discover_sources` is invoked
    with ``allow_network=True`` (fail closed), mirroring the ingestion and
    enrichment pipeline guards.
    """


def preference_score(kind: str, risk: str) -> float:
    """Deterministic preference score (higher = surfaced first)."""
    return KIND_WEIGHT.get(kind, 0.0) - RISK_PENALTY.get(risk, 0.0)


@dataclass(frozen=True)
class CandidateSource:
    """A descriptor of *where* to look for leads, derived from a `SearchPlan`.

    `kind` places it on the preference ladder, `name` is human-readable, `query`
    is the concrete query/endpoint hint to act on later, `risk` flags
    responsible-use concerns, `requires_network` marks that *acting* on it will
    touch the network, `rationale` records why it was chosen, `score` is the
    deterministic preference value, and `rank` is its 0-based position after
    ranking (-1 = not yet ranked). Immutable so it can be safely passed down the
    pipeline.
    """

    kind: str = ""
    name: str = ""
    query: str = ""
    risk: str = "low"
    requires_network: bool = False
    rationale: str = ""
    score: float = 0.0
    rank: int = -1

    # Column order shared by any future SQLite table and its derived CSV mirror.
    COLUMNS = (
        "kind",
        "name",
        "query",
        "risk",
        "requires_network",
        "rationale",
        "score",
        "rank",
    )

    @classmethod
    def make(
        cls,
        *,
        kind: str,
        name: str,
        query: str,
        risk: str = "low",
        requires_network: bool = False,
        rationale: str = "",
        rank: int = -1,
    ) -> "CandidateSource":
        """Build a `CandidateSource`, validating vocab and deriving `score`."""
        if kind not in KINDS:
            raise DiscoveryError(f"unknown candidate kind: {kind!r}")
        if risk not in RISK_LEVELS:
            raise DiscoveryError(f"unknown risk level: {risk!r}")
        return cls(
            kind=kind,
            name=(name or "").strip(),
            query=(query or "").strip(),
            risk=risk,
            requires_network=bool(requires_network),
            rationale=(rationale or "").strip(),
            score=preference_score(kind, risk),
            rank=int(rank),
        )

    def to_row(self) -> Mapping[str, str]:
        """Flatten to a string-keyed row (SQLite/CSV friendly, round-trips)."""
        return {
            "kind": self.kind,
            "name": self.name,
            "query": self.query,
            "risk": self.risk,
            "requires_network": "1" if self.requires_network else "0",
            "rationale": self.rationale,
            "score": json.dumps(self.score),
            "rank": str(self.rank),
        }

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "CandidateSource":
        """Inverse of `to_row`."""
        return cls(
            kind=str(row.get("kind", "")),
            name=str(row.get("name", "")),
            query=str(row.get("query", "")),
            risk=str(row.get("risk", "")) or "low",
            requires_network=str(row.get("requires_network", "")) in ("1", "True", "true"),
            rationale=str(row.get("rationale", "")),
            score=float(json.loads(row["score"])) if row.get("score") not in (None, "") else 0.0,
            rank=int(row.get("rank", -1)),
        )


def rank_candidates(candidates: Iterable[CandidateSource]) -> List[CandidateSource]:
    """Sort candidates by preference and reassign a stable 0-based `rank`.

    Order: score desc, then name asc, then query asc — fully deterministic, no
    clocks or RNG. Returns new `CandidateSource` instances (the dataclass is
    frozen) with `rank` set to position.
    """
    ordered = sorted(candidates, key=lambda c: (-c.score, c.name, c.query))
    return [replace(c, rank=i) for i, c in enumerate(ordered)]


class SourceDiscoverer(abc.ABC):
    """The single discovery seam: take a `SearchPlan`, return candidate sources.

    The deterministic baseline (`RuleSourceDiscoverer`) keeps
    ``requires_network = False`` and performs no I/O. A future network-backed
    discoverer would set it ``True`` and only run behind the opt-in.
    """

    #: Human-readable discoverer name.
    name: str = "source_discoverer"

    #: Whether running this discoverer performs network access (opt-in gated).
    requires_network: bool = False

    @abc.abstractmethod
    def discover(self, plan) -> List[CandidateSource]:
        """Return candidate sources for ``plan``. Baselines must not need network."""
        raise NotImplementedError

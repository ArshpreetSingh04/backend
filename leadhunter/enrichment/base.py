"""Enrichment contract: fill missing identity fields behind one seam.

M2's *enrichment* half (distinct from *scoring*) takes a persisted `Lead` and
returns an `EnrichResult` whose `lead` may have previously-empty identity fields
populated. Every enricher implements the same small `IdentityEnricher`
interface so a deterministic no-network enricher and any future opt-in network
enricher are interchangeable.

Terminology note: scoring's ``scoring/base.py`` defines a separate ``Enricher``
ABC that returns a `Score`. This module's `IdentityEnricher` is a *different*
contract — it fills fields rather than scoring — and lives in its own package to
avoid any collision.

Responsible-use: an enricher that sets ``requires_network = True`` is refused by
the driver unless the caller opts in (fail-closed), mirroring the ingestion
pipeline's network guard.

Stdlib-only (``abc``, ``dataclasses``).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Tuple

from ..ingestion.model import Lead


class EnrichmentNetworkNotAllowedError(RuntimeError):
    """Raised when a network-requiring enricher runs without an explicit opt-in.

    Responsible-use contract: network access is opt-in only. Enrichers that set
    ``requires_network = True`` may only run when the driver is invoked with
    ``allow_network=True``.
    """


@dataclass(frozen=True)
class EnrichResult:
    """Outcome of enriching one lead.

    `lead` is the (possibly updated) lead — a new `Lead` when fields were
    filled, otherwise the original unchanged. `filled` names the fields newly
    populated, and `method` records who produced the result (e.g. "derive").
    Immutable so it can be safely passed around and handed to a later
    persistence step.
    """

    lead: Lead
    filled: Tuple[str, ...]
    method: str

    @property
    def changed(self) -> bool:
        """True when at least one field was filled."""
        return bool(self.filled)


class IdentityEnricher(abc.ABC):
    """The single enrichment seam: take a `Lead`, return an `EnrichResult`.

    Implementations must be safe to call without network access unless they
    declare ``requires_network = True``, in which case the driver gates them
    behind the responsible-use opt-in. Enrichers must only ever *fill empty*
    identity fields — never overwrite existing values — and must preserve the
    lead's ``dedup_key`` so persistence identity is stable.
    """

    #: Human-readable enricher name, also recorded as the result's method.
    name: str = "enricher"

    #: Whether running this enricher performs network access (opt-in gated).
    requires_network: bool = False

    @abc.abstractmethod
    def enrich(self, lead: Lead) -> EnrichResult:
        """Return an `EnrichResult` for ``lead``."""
        raise NotImplementedError

"""Deterministic, no-network enrichment: derive missing fields from present ones.

`DerivationEnricher` is the guaranteed default path for M2 enrichment: a pure
function of the fields already on a `Lead`. It needs no enrichment data, performs
no I/O, and always returns the same result for the same input. It only ever
*fills empty* fields and never changes the lead's ``dedup_key``.

Currently it derives the structured ``domain`` field, which is logically
implied by other identity fields:

- ``domain`` from ``email`` — the part after ``@``.
- ``domain`` from ``source_url`` — the host, when no email is available.

Fields that cannot be derived deterministically (e.g. email or phone) are out of
scope here; they belong to a later, opt-in network enricher. Stdlib-only
(``dataclasses``, ``urllib.parse``).
"""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlsplit

from ..ingestion.model import Lead
from .base import EnrichResult, IdentityEnricher


def _domain_from_email(email: str) -> str:
    """Return the lowercased domain part of an email, or "" if not derivable."""
    if "@" not in email:
        return ""
    domain = email.rsplit("@", 1)[1].strip().casefold()
    return domain


def _domain_from_url(url: str) -> str:
    """Return the lowercased host of a URL (no ``www.``/port), or "" if none."""
    text = url.strip()
    if not text:
        return ""
    # urlsplit needs a scheme to populate netloc; assume http:// if missing.
    if "://" not in text:
        text = "http://" + text
    host = urlsplit(text).hostname or ""
    host = host.strip().casefold()
    if host.startswith("www."):
        host = host[4:]
    return host


class DerivationEnricher(IdentityEnricher):
    """Fill empty structured fields that are implied by present identity fields."""

    name = "derive"
    requires_network = False

    def enrich(self, lead: Lead) -> EnrichResult:
        updates = {}

        if not (lead.domain or "").strip():
            domain = _domain_from_email(lead.email or "")
            if not domain:
                domain = _domain_from_url(lead.source_url or "")
            if domain:
                updates["domain"] = domain

        if not updates:
            return EnrichResult(lead=lead, filled=(), method=self.name)

        # Preserve dedup_key explicitly: filling fields must not re-key the lead.
        new_lead = replace(lead, dedup_key=lead.dedup_key, **updates)
        return EnrichResult(
            lead=new_lead,
            filled=tuple(sorted(updates)),
            method=self.name,
        )

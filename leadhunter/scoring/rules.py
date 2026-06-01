"""Deterministic, no-network baseline scorer.

`RuleScorer` is the guaranteed floor for M2: a pure function of the identity
fields already present on a `Lead`. It needs no enrichment data, performs no
I/O, and always returns the same `Score` for the same input. Stdlib-only.
"""

from __future__ import annotations

from ..ingestion.model import Lead
from .base import Enricher, Score


# Local parts that signal a role/shared mailbox rather than a person.
_ROLE_LOCAL_PARTS = {
    "info",
    "sales",
    "contact",
    "support",
    "admin",
    "hello",
    "office",
    "team",
    "help",
    "enquiries",
    "inquiries",
    "marketing",
    "billing",
    "noreply",
    "no-reply",
}

# Point weights for each identity signal.
_EMAIL_POINTS = 30
_ROLE_EMAIL_POINTS = 10
_DOMAIN_POINTS = 20
_COMPANY_POINTS = 15
_NAME_POINTS = 15
_PHONE_POINTS = 10
_SOURCE_URL_POINTS = 10


def _is_role_email(email: str) -> bool:
    """True if the email's local part looks like a role/shared mailbox."""
    local = email.split("@", 1)[0].strip().casefold()
    return local in _ROLE_LOCAL_PARTS


class RuleScorer(Enricher):
    """Transparent weighted scoring over identity completeness/quality."""

    name = "rules"

    def score(self, lead: Lead) -> Score:
        points = 0
        reasons = []

        email = (lead.email or "").strip()
        if email:
            if _is_role_email(email):
                points += _ROLE_EMAIL_POINTS
                reasons.append(
                    f"role/shared email (+{_ROLE_EMAIL_POINTS})"
                )
            else:
                points += _EMAIL_POINTS
                reasons.append(f"personal email (+{_EMAIL_POINTS})")

        if (lead.domain or "").strip():
            points += _DOMAIN_POINTS
            reasons.append(f"domain (+{_DOMAIN_POINTS})")

        if (lead.company or "").strip():
            points += _COMPANY_POINTS
            reasons.append(f"company (+{_COMPANY_POINTS})")

        if (lead.name or "").strip():
            points += _NAME_POINTS
            reasons.append(f"contact name (+{_NAME_POINTS})")

        if (lead.phone or "").strip():
            points += _PHONE_POINTS
            reasons.append(f"phone (+{_PHONE_POINTS})")

        if (lead.source_url or "").strip():
            points += _SOURCE_URL_POINTS
            reasons.append(f"source url (+{_SOURCE_URL_POINTS})")

        if not reasons:
            reasons.append("no identifying fields")

        return Score.make(points, reasons, self.name)

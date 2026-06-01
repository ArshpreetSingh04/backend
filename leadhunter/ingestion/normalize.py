"""Normalization and in-memory dedup for raw lead payloads.

Pure functions (no I/O, no network): turn an arbitrary source dict into a
clean `Lead`, and collapse a list of leads on their dedup key while
preserving first-seen order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, List, Mapping, Optional

from .model import Lead, _norm_email


def _clean(value: Optional[Any]) -> str:
    """Trim a scalar field; collapse None to empty string."""
    if value is None:
        return ""
    return str(value).strip()


def _derive_domain(domain: Optional[str], email: str) -> str:
    """Use an explicit domain, else fall back to the email's domain part."""
    d = _clean(domain).casefold()
    if d:
        return d
    if "@" in email:
        return email.split("@", 1)[1]
    return ""


def normalize_lead(
    raw: Mapping[str, Any], *, first_seen_at: Optional[str] = None
) -> Lead:
    """Build a normalized `Lead` from an arbitrary source payload."""
    email = _norm_email(raw.get("email"))
    domain = _derive_domain(raw.get("domain"), email)
    seen = first_seen_at or datetime.now(timezone.utc).isoformat()
    return Lead(
        name=_clean(raw.get("name")),
        company=_clean(raw.get("company")),
        email=email,
        domain=domain,
        phone=_clean(raw.get("phone")),
        source=_clean(raw.get("source")),
        source_url=_clean(raw.get("source_url")),
        raw=dict(raw),
        first_seen_at=seen,
    )


def dedup(leads: Iterable[Lead]) -> List[Lead]:
    """Collapse leads on `dedup_key`, keeping the first occurrence."""
    seen = set()
    result: List[Lead] = []
    for lead in leads:
        if lead.dedup_key in seen:
            continue
        seen.add(lead.dedup_key)
        result.append(lead)
    return result

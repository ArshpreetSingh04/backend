"""Core Lead data model and dedup-key strategy.

Stdlib-only. The dedup key is deterministic and layered so that the same
real-world lead always maps to the same key regardless of casing/whitespace.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Mapping, Optional


# Legal/company suffixes stripped when normalizing a company name.
_COMPANY_SUFFIXES = {
    "inc",
    "incorporated",
    "llc",
    "l.l.c",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "co",
    "company",
    "gmbh",
    "plc",
    "llp",
    "lp",
    "pllc",
    "sa",
    "ag",
}

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def _norm_text(value: Optional[str]) -> str:
    """Casefold, strip punctuation, and collapse whitespace."""
    if not value:
        return ""
    text = _PUNCT_RE.sub(" ", str(value))
    text = _WS_RE.sub(" ", text).strip()
    return text.casefold()


def _norm_email(value: Optional[str]) -> str:
    """Lowercase and trim an email address."""
    if not value:
        return ""
    return str(value).strip().casefold()


def _norm_domain(value: Optional[str]) -> str:
    """Lowercase/trim a domain, drop a leading 'www.'. Dots are preserved."""
    if not value:
        return ""
    d = str(value).strip().casefold()
    if d.startswith("www."):
        d = d[4:]
    return d


def normalize_company(value: Optional[str]) -> str:
    """Normalize a company name and strip trailing legal suffixes."""
    text = _norm_text(value)
    if not text:
        return ""
    tokens = text.split(" ")
    while tokens and tokens[-1].strip(".") in _COMPANY_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def compute_dedup_key(
    email: Optional[str],
    domain: Optional[str],
    company: Optional[str],
    name: Optional[str],
) -> str:
    """Deterministic, layered dedup key. First non-empty layer wins.

    1. email (lowercased)
    2. domain + normalized company
    3. normalized company + normalized name
    4. sha1 hash of the sorted normalized field tuple (last-resort fallback)
    """
    email_n = _norm_email(email)
    if email_n:
        return f"email:{email_n}"

    domain_n = _norm_domain(domain)
    company_n = normalize_company(company)
    if domain_n and company_n:
        return f"domain+company:{domain_n}|{company_n}"

    name_n = _norm_text(name)
    if company_n and name_n:
        return f"company+name:{company_n}|{name_n}"

    fallback = "|".join(sorted([email_n, domain_n, company_n, name_n]))
    digest = hashlib.sha1(fallback.encode("utf-8")).hexdigest()
    return f"hash:{digest}"


@dataclass
class Lead:
    """A single prospective lead.

    `dedup_key` is computed from the identity fields if not supplied.
    `raw` holds the original source payload (JSON-serialized in SQLite).
    """

    name: str = ""
    company: str = ""
    email: str = ""
    domain: str = ""
    phone: str = ""
    source: str = ""
    source_url: str = ""
    raw: Mapping[str, Any] = field(default_factory=dict)
    first_seen_at: str = ""
    dedup_key: str = ""

    def __post_init__(self) -> None:
        if not self.dedup_key:
            self.dedup_key = compute_dedup_key(
                self.email, self.domain, self.company, self.name
            )

    # Column order used by both SQLite and the derived CSV mirror.
    COLUMNS = (
        "dedup_key",
        "name",
        "company",
        "email",
        "domain",
        "phone",
        "source",
        "source_url",
        "raw",
        "first_seen_at",
    )

    def to_row(self) -> dict:
        """Serialize to a flat row dict (raw -> JSON string)."""
        data = asdict(self)
        data["raw"] = json.dumps(self.raw, sort_keys=True, ensure_ascii=False)
        return {col: data[col] for col in self.COLUMNS}

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Lead":
        """Rebuild a Lead from a flat row dict (raw JSON string -> dict)."""
        raw_value = row.get("raw") or "{}"
        if isinstance(raw_value, str):
            raw_obj = json.loads(raw_value) if raw_value else {}
        else:
            raw_obj = dict(raw_value)
        return cls(
            name=row.get("name", "") or "",
            company=row.get("company", "") or "",
            email=row.get("email", "") or "",
            domain=row.get("domain", "") or "",
            phone=row.get("phone", "") or "",
            source=row.get("source", "") or "",
            source_url=row.get("source_url", "") or "",
            raw=raw_obj,
            first_seen_at=row.get("first_seen_at", "") or "",
            dedup_key=row.get("dedup_key", "") or "",
        )

"""LeadHunter ingestion package.

M1 Increment 1: core Lead model, normalization/dedup, and a dual-sink
persistence layer (SQLite as source of truth, CSV as a derived mirror).

Stdlib-only. No external network access.
"""

from .model import Lead
from .normalize import normalize_lead, dedup
from .persistence import LeadStore

__all__ = ["Lead", "normalize_lead", "dedup", "LeadStore"]

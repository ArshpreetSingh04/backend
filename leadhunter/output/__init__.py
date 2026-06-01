"""LeadHunter output (M2): consolidate ingestion + enrichment + scoring.

This is the *feedback* slice — it joins the three dual-sink stores into a single,
actionable qualified-leads output (best-known identity + qualification score +
provenance), sorted so the hottest leads surface first.

Public surface:
- `QualifiedLead` — the consolidated, flat output record.
- `assemble_qualified` / `QualifiedSummary` — the read-only join + its summary.
- `QualifiedLeadStore` — dual-sink persistence (SQLite truth + CSV mirror).
- `build_qualified_output` — assemble-and-persist driver.
"""

from .assemble import QualifiedSummary, assemble_qualified
from .base import QualifiedLead
from .output_store import QualifiedLeadStore, build_qualified_output

__all__ = [
    "QualifiedLead",
    "QualifiedSummary",
    "assemble_qualified",
    "QualifiedLeadStore",
    "build_qualified_output",
]

"""Dual-sink persistence for enriched leads: SQLite truth + derived CSV mirror.

Mirrors the `ScoreStore`/`LeadStore` pattern (additively, in its own table and
file): enriched leads are upserted into an ``enriched_leads`` SQLite table keyed
by ``dedup_key``; after every write the CSV mirror is regenerated *from* SQLite
so the two never diverge.

This is the persistence half of M2's enrichment slice. `enrich_all()`
(``enrichment/pipeline.py``) is read-only w.r.t. the ingestion `LeadStore` and
hands back a list of `EnrichResult`s; `persist_enrichments()` here consumes those
results and writes them to a *separate* ``enriched_leads`` store, so the M1
``leads`` table is never mutated.

Reconciliation is **fill-only**, matching the enricher's own semantics: an upsert
of an already-present ``dedup_key`` only populates columns that are currently
empty (never overwriting a non-empty value), unions the recorded ``filled`` field
names, and refreshes ``method``/``enriched_at``.

Stdlib-only (``sqlite3``, ``csv``, ``json``, ``datetime``); no network.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from ..ingestion.model import Lead
from ..ingestion.persistence import LeadStore
from .base import EnrichResult, IdentityEnricher
from .pipeline import enrich_all


# The enriched lead snapshot (Lead.COLUMNS) plus enrichment metadata. Shared by
# SQLite and the derived CSV mirror.
META_COLUMNS = ("filled", "method", "enriched_at")
COLUMNS = tuple(Lead.COLUMNS) + META_COLUMNS

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS enriched_leads (
    dedup_key     TEXT PRIMARY KEY,
    name          TEXT NOT NULL DEFAULT '',
    company       TEXT NOT NULL DEFAULT '',
    email         TEXT NOT NULL DEFAULT '',
    domain        TEXT NOT NULL DEFAULT '',
    phone         TEXT NOT NULL DEFAULT '',
    source        TEXT NOT NULL DEFAULT '',
    source_url    TEXT NOT NULL DEFAULT '',
    raw           TEXT NOT NULL DEFAULT '{}',
    first_seen_at TEXT NOT NULL DEFAULT '',
    filled        TEXT NOT NULL DEFAULT '[]',
    method        TEXT NOT NULL DEFAULT '',
    enriched_at   TEXT NOT NULL DEFAULT ''
);
"""

# Lead identity/value columns that fill-only reconcile may populate when empty.
# dedup_key is the stable PK and is never changed; raw/first_seen_at are the
# original ingestion snapshot and are only set on first insert.
_FILLABLE = ("name", "company", "email", "domain", "phone", "source", "source_url")


def _now_iso() -> str:
    """UTC timestamp in ISO-8601 (seconds resolution)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class EnrichmentStore:
    """Persist enriched leads to SQLite (truth) and a derived CSV mirror."""

    def __init__(self, db_path: str, csv_path: str) -> None:
        self.db_path = str(db_path)
        self.csv_path = str(csv_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.csv_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        # Ensure the CSV mirror exists even before the first write.
        self.sync_csv()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_SQL)
            conn.commit()

    def upsert(self, result: EnrichResult, *, enriched_at: str = "") -> bool:
        """Insert or fill-only-merge an `EnrichResult`; return whether the row changed.

        New ``dedup_key`` -> insert the enriched lead snapshot + metadata.
        Existing ``dedup_key`` -> only populate columns that are currently empty
        (never overwrite a non-empty value), union the ``filled`` field names, and
        refresh ``method``/``enriched_at``. The CSV mirror is rebuilt afterward.
        """
        lead = result.lead
        key = lead.dedup_key
        stamp = enriched_at or _now_iso()
        new_filled = list(result.filled)

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM enriched_leads WHERE dedup_key = ?", (key,)
            ).fetchone()

            if existing is None:
                row = lead.to_row()
                row["filled"] = json.dumps(new_filled, ensure_ascii=False)
                row["method"] = result.method
                row["enriched_at"] = stamp
                conn.execute(
                    """
                    INSERT INTO enriched_leads
                        (dedup_key, name, company, email, domain, phone,
                         source, source_url, raw, first_seen_at,
                         filled, method, enriched_at)
                    VALUES
                        (:dedup_key, :name, :company, :email, :domain, :phone,
                         :source, :source_url, :raw, :first_seen_at,
                         :filled, :method, :enriched_at)
                    """,
                    row,
                )
                conn.commit()
                self.sync_csv()
                return True

            # Fill-only reconcile against the existing row.
            incoming = lead.to_row()
            updates = {}
            for col in _FILLABLE:
                if not (existing[col] or "").strip() and (incoming[col] or "").strip():
                    updates[col] = incoming[col]

            prev_filled = json.loads(existing["filled"] or "[]")
            merged_filled = sorted(set(prev_filled) | set(new_filled))
            filled_changed = merged_filled != list(prev_filled)
            method_changed = result.method != (existing["method"] or "")

            changed = bool(updates) or filled_changed
            if not changed and not method_changed:
                return False

            updates["filled"] = json.dumps(merged_filled, ensure_ascii=False)
            updates["method"] = result.method
            updates["enriched_at"] = stamp
            updates["dedup_key"] = key
            set_clause = ", ".join(f"{col} = :{col}" for col in updates if col != "dedup_key")
            conn.execute(
                f"UPDATE enriched_leads SET {set_clause} WHERE dedup_key = :dedup_key",
                updates,
            )
            conn.commit()
        self.sync_csv()
        return changed

    def all(self) -> List[Tuple[Lead, dict]]:
        """Read all enriched leads back from SQLite as ``(Lead, metadata)`` pairs."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM enriched_leads ORDER BY first_seen_at, dedup_key"
            )
            pairs: List[Tuple[Lead, dict]] = []
            for r in cursor.fetchall():
                row = dict(r)
                meta = {
                    "filled": json.loads(row.get("filled") or "[]"),
                    "method": row.get("method", "") or "",
                    "enriched_at": row.get("enriched_at", "") or "",
                }
                pairs.append((Lead.from_row(row), meta))
            return pairs

    def count(self) -> int:
        with self._connect() as conn:
            (n,) = conn.execute("SELECT COUNT(*) FROM enriched_leads").fetchone()
            return int(n)

    def sync_csv(self) -> None:
        """Regenerate the CSV mirror from the current SQLite contents."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM enriched_leads ORDER BY first_seen_at, dedup_key"
            )
            rows = [dict(r) for r in cursor.fetchall()]
        with open(self.csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(COLUMNS))
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row[col] for col in COLUMNS})

    def read_csv(self) -> List[dict]:
        """Read enriched rows back from the CSV mirror (helper for verification)."""
        with open(self.csv_path, "r", newline="", encoding="utf-8") as fh:
            return [dict(r) for r in csv.DictReader(fh)]


def persist_enrichments(
    results: Iterable[EnrichResult],
    store: EnrichmentStore,
    *,
    enriched_at: str = "",
) -> int:
    """Persist `EnrichResult`s (from `enrich_all()`) via ``store``.

    Returns the number of rows that were inserted or changed. Idempotent: a
    second pass over the same results changes nothing (fill-only reconcile).
    """
    changed = 0
    for result in results:
        if store.upsert(result, enriched_at=enriched_at):
            changed += 1
    return changed


def enrich_and_persist(
    lead_store: LeadStore,
    enricher: IdentityEnricher,
    store: EnrichmentStore,
    *,
    allow_network: bool = False,
    enriched_at: str = "",
) -> Tuple[int, int]:
    """Convenience: ``enrich_all`` -> ``persist_enrichments`` in one call.

    Returns ``(processed, persisted)``. Propagates the read-only enrichment driver
    and its fail-closed network opt-in: a ``requires_network`` enricher is refused
    unless ``allow_network=True``. Performs no network I/O of its own.
    """
    summary, results = enrich_all(lead_store, enricher, allow_network=allow_network)
    persisted = persist_enrichments(results, store, enriched_at=enriched_at)
    return summary.processed, persisted

"""Dual-sink persistence for the consolidated output: SQLite truth + CSV mirror.

Mirrors the `LeadStore`/`ScoreStore`/`EnrichmentStore` pattern (additively, in its
own ``qualified_leads`` table and file). Unlike the enrichment store's fill-only
reconcile, a `QualifiedLead` is a **fully derived snapshot** of the current join,
so `upsert()` overwrites the whole row for a ``dedup_key`` — re-running the build
after a rescore/re-enrichment refreshes the output without creating duplicates.

`build_qualified_output()` is the driver: assemble the join (read-only across the
three source stores) and persist it here. Stdlib-only (``sqlite3``, ``csv``,
``json``); no network.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import List, Tuple

from ..ingestion.persistence import LeadStore
from .assemble import QualifiedSummary, assemble_qualified
from .base import QualifiedLead

COLUMNS = QualifiedLead.COLUMNS

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS qualified_leads (
    dedup_key         TEXT PRIMARY KEY,
    name              TEXT NOT NULL DEFAULT '',
    company           TEXT NOT NULL DEFAULT '',
    email             TEXT NOT NULL DEFAULT '',
    domain            TEXT NOT NULL DEFAULT '',
    phone             TEXT NOT NULL DEFAULT '',
    source            TEXT NOT NULL DEFAULT '',
    source_url        TEXT NOT NULL DEFAULT '',
    first_seen_at     TEXT NOT NULL DEFAULT '',
    score             INTEGER NOT NULL DEFAULT 0,
    tier              TEXT NOT NULL DEFAULT '',
    reasons           TEXT NOT NULL DEFAULT '[]',
    score_method      TEXT NOT NULL DEFAULT '',
    enrichment_method TEXT NOT NULL DEFAULT '',
    filled            TEXT NOT NULL DEFAULT '[]'
);
"""


class QualifiedLeadStore:
    """Persist `QualifiedLead`s to SQLite (truth) and a derived CSV mirror."""

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

    def upsert(self, qualified: QualifiedLead) -> bool:
        """Insert or overwrite the row for ``qualified.dedup_key``.

        Returns whether the stored row changed (new key, or any column differs).
        The whole row is replaced because a `QualifiedLead` is a fully derived
        snapshot of the current join. The CSV mirror is rebuilt afterward.
        """
        row = qualified.to_row()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM qualified_leads WHERE dedup_key = ?",
                (qualified.dedup_key,),
            ).fetchone()
            if existing is not None:
                same = all(existing[col] == row[col] for col in COLUMNS)
                if same:
                    return False
            conn.execute(
                """
                INSERT INTO qualified_leads
                    (dedup_key, name, company, email, domain, phone, source,
                     source_url, first_seen_at, score, tier, reasons,
                     score_method, enrichment_method, filled)
                VALUES
                    (:dedup_key, :name, :company, :email, :domain, :phone, :source,
                     :source_url, :first_seen_at, :score, :tier, :reasons,
                     :score_method, :enrichment_method, :filled)
                ON CONFLICT(dedup_key) DO UPDATE SET
                    name=excluded.name,
                    company=excluded.company,
                    email=excluded.email,
                    domain=excluded.domain,
                    phone=excluded.phone,
                    source=excluded.source,
                    source_url=excluded.source_url,
                    first_seen_at=excluded.first_seen_at,
                    score=excluded.score,
                    tier=excluded.tier,
                    reasons=excluded.reasons,
                    score_method=excluded.score_method,
                    enrichment_method=excluded.enrichment_method,
                    filled=excluded.filled
                """,
                row,
            )
            conn.commit()
        self.sync_csv()
        return True

    def all(self) -> List[QualifiedLead]:
        """Read all rows back from SQLite, most actionable (highest score) first."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM qualified_leads ORDER BY score DESC, dedup_key"
            )
            return [QualifiedLead.from_row(dict(r)) for r in cursor.fetchall()]

    def count(self) -> int:
        with self._connect() as conn:
            (n,) = conn.execute("SELECT COUNT(*) FROM qualified_leads").fetchone()
            return int(n)

    def sync_csv(self) -> None:
        """Regenerate the CSV mirror from the current SQLite contents."""
        rows = [q.to_row() for q in self.all()]
        with open(self.csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(COLUMNS))
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row[col] for col in COLUMNS})

    def read_csv(self) -> List[QualifiedLead]:
        """Read rows back from the CSV mirror (helper for verification)."""
        with open(self.csv_path, "r", newline="", encoding="utf-8") as fh:
            return [QualifiedLead.from_row(row) for row in csv.DictReader(fh)]


def build_qualified_output(
    lead_store: LeadStore,
    qualified_store: QualifiedLeadStore,
    *,
    enrichment_store=None,
    score_store=None,
) -> Tuple[QualifiedSummary, int]:
    """Assemble the join and persist it via ``qualified_store``.

    Returns ``(summary, written)`` where ``written`` is the number of rows
    inserted or changed. Idempotent: re-running with unchanged inputs writes
    nothing. Read-only across the three source stores; no network I/O.
    """
    summary, qualified = assemble_qualified(
        lead_store,
        enrichment_store=enrichment_store,
        score_store=score_store,
    )
    written = 0
    for q in qualified:
        if qualified_store.upsert(q):
            written += 1
    return summary, written

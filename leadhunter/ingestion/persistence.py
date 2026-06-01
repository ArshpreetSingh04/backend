"""Dual-sink persistence: SQLite is the source of truth; CSV is a mirror.

Leads are written to SQLite idempotently (UNIQUE dedup_key). After every
write the CSV is regenerated *from* SQLite, so the two sinks can never
diverge. Stdlib-only (sqlite3, csv, json); no network.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable, List

from .model import Lead


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    dedup_key     TEXT PRIMARY KEY,
    name          TEXT NOT NULL DEFAULT '',
    company       TEXT NOT NULL DEFAULT '',
    email         TEXT NOT NULL DEFAULT '',
    domain        TEXT NOT NULL DEFAULT '',
    phone         TEXT NOT NULL DEFAULT '',
    source        TEXT NOT NULL DEFAULT '',
    source_url    TEXT NOT NULL DEFAULT '',
    raw           TEXT NOT NULL DEFAULT '{}',
    first_seen_at TEXT NOT NULL DEFAULT ''
);
"""


class LeadStore:
    """Persist leads to SQLite (truth) and a derived CSV mirror."""

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

    def add(self, leads: Iterable[Lead]) -> int:
        """Insert leads idempotently. Returns the count newly inserted.

        Existing dedup keys are ignored (INSERT OR IGNORE), so re-ingesting
        the same lead never creates duplicates. The CSV mirror is rebuilt
        from SQLite afterward.
        """
        rows = [lead.to_row() for lead in leads]
        inserted = 0
        with self._connect() as conn:
            for row in rows:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO leads
                        (dedup_key, name, company, email, domain, phone,
                         source, source_url, raw, first_seen_at)
                    VALUES
                        (:dedup_key, :name, :company, :email, :domain, :phone,
                         :source, :source_url, :raw, :first_seen_at)
                    """,
                    row,
                )
                inserted += cur.rowcount
            conn.commit()
        self.sync_csv()
        return inserted

    def all(self) -> List[Lead]:
        """Read all leads back from SQLite (the source of truth)."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM leads ORDER BY first_seen_at, dedup_key"
            )
            return [Lead.from_row(dict(r)) for r in cursor.fetchall()]

    def count(self) -> int:
        with self._connect() as conn:
            (n,) = conn.execute("SELECT COUNT(*) FROM leads").fetchone()
            return int(n)

    def sync_csv(self) -> None:
        """Regenerate the CSV mirror from the current SQLite contents."""
        leads = self.all()
        with open(self.csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(Lead.COLUMNS))
            writer.writeheader()
            for lead in leads:
                writer.writerow(lead.to_row())

    def read_csv(self) -> List[Lead]:
        """Read leads back from the CSV mirror (helper for verification)."""
        with open(self.csv_path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            return [Lead.from_row(row) for row in reader]

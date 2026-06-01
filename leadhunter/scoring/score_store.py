"""Dual-sink persistence for scores: SQLite truth + derived CSV mirror.

Mirrors the `LeadStore` pattern (additively, in its own table/file): scores are
upserted into a ``lead_scores`` SQLite table keyed by ``dedup_key``; after every
write the CSV mirror is regenerated *from* SQLite so the two never diverge.

`score_all()` is the driver: read leads from a `LeadStore`, score each with any
`Enricher`, and persist the results. Stdlib-only (``sqlite3``, ``csv``, ``json``);
no network.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Tuple

from ..ingestion.persistence import LeadStore
from .base import Enricher, Score


# Column order shared by SQLite and the derived CSV mirror.
COLUMNS = ("dedup_key", "score", "tier", "reasons", "method", "scored_at")

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS lead_scores (
    dedup_key TEXT PRIMARY KEY,
    score     INTEGER NOT NULL DEFAULT 0,
    tier      TEXT NOT NULL DEFAULT '',
    reasons   TEXT NOT NULL DEFAULT '[]',
    method    TEXT NOT NULL DEFAULT '',
    scored_at TEXT NOT NULL DEFAULT ''
);
"""


def _now_iso() -> str:
    """UTC timestamp in ISO-8601 (seconds resolution)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ScoreStore:
    """Persist scores to SQLite (truth) and a derived CSV mirror."""

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

    def upsert(self, dedup_key: str, score: Score, *, scored_at: str = "") -> None:
        """Insert or update the score for ``dedup_key`` (rescoring overwrites)."""
        row = {
            "dedup_key": dedup_key,
            "score": int(score.value),
            "tier": score.tier,
            "reasons": json.dumps(list(score.reasons), ensure_ascii=False),
            "method": score.method,
            "scored_at": scored_at or _now_iso(),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO lead_scores
                    (dedup_key, score, tier, reasons, method, scored_at)
                VALUES
                    (:dedup_key, :score, :tier, :reasons, :method, :scored_at)
                ON CONFLICT(dedup_key) DO UPDATE SET
                    score=excluded.score,
                    tier=excluded.tier,
                    reasons=excluded.reasons,
                    method=excluded.method,
                    scored_at=excluded.scored_at
                """,
                row,
            )
            conn.commit()
        self.sync_csv()

    def all(self) -> List[dict]:
        """Read all score rows back from SQLite (the source of truth)."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM lead_scores ORDER BY score DESC, dedup_key"
            )
            return [dict(r) for r in cursor.fetchall()]

    def count(self) -> int:
        with self._connect() as conn:
            (n,) = conn.execute("SELECT COUNT(*) FROM lead_scores").fetchone()
            return int(n)

    def sync_csv(self) -> None:
        """Regenerate the CSV mirror from the current SQLite contents."""
        rows = self.all()
        with open(self.csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(COLUMNS))
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row[col] for col in COLUMNS})

    def read_csv(self) -> List[dict]:
        """Read score rows back from the CSV mirror (helper for verification)."""
        with open(self.csv_path, "r", newline="", encoding="utf-8") as fh:
            return [dict(r) for r in csv.DictReader(fh)]


def score_all(
    lead_store: LeadStore,
    score_store: ScoreStore,
    scorer: Enricher,
) -> Tuple[int, List[Score]]:
    """Score every lead in ``lead_store`` and persist via ``score_store``.

    Returns ``(count, scores)``. Deterministic given a deterministic scorer;
    performs no network I/O of its own.
    """
    scores: List[Score] = []
    for lead in lead_store.all():
        score = scorer.score(lead)
        score_store.upsert(lead.dedup_key, score)
        scores.append(score)
    return len(scores), scores

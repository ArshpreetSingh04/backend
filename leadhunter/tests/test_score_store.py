"""Hermetic tests for ScoreStore + score_all — dual-sink integrity, no network."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.ingestion.normalize import normalize_lead
from leadhunter.ingestion.persistence import LeadStore
from leadhunter.scoring.base import Score
from leadhunter.scoring.rules import RuleScorer
from leadhunter.scoring.score_store import ScoreStore, score_all


class ScoreStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = os.path.join(self.tmp.name, "scores.db")
        self.csv = os.path.join(self.tmp.name, "scores.csv")

    def _store(self):
        return ScoreStore(self.db, self.csv)

    def test_csv_exists_before_first_write(self):
        store = self._store()
        self.assertTrue(os.path.exists(self.csv))
        self.assertEqual(store.read_csv(), [])

    def test_upsert_persists_and_mirror_matches(self):
        store = self._store()
        score = Score.make(70, ["personal email (+30)", "domain (+20)"], "rules")
        store.upsert("email:jane@example.com", score, scored_at="2026-06-01T00:00:00+00:00")

        rows = store.all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["score"], 70)
        self.assertEqual(rows[0]["tier"], "hot")
        self.assertEqual(json.loads(rows[0]["reasons"]), list(score.reasons))

        # CSV mirror must equal SQLite truth.
        self.assertEqual(store.read_csv(), [{k: str(v) for k, v in store.all()[0].items()}])

    def test_upsert_is_idempotent_and_overwrites_on_rescore(self):
        store = self._store()
        key = "email:jane@example.com"
        store.upsert(key, Score.make(40, ["a"], "rules"))
        store.upsert(key, Score.make(90, ["b"], "llm:fake"))
        self.assertEqual(store.count(), 1)
        row = store.all()[0]
        self.assertEqual(row["score"], 90)
        self.assertEqual(row["method"], "llm:fake")

    def test_persists_across_reopen(self):
        store = self._store()
        store.upsert("k", Score.make(55, ["x"], "rules"))
        reopened = ScoreStore(self.db, self.csv)
        self.assertEqual(reopened.count(), 1)


class ScoreAllTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lead_store = LeadStore(
            os.path.join(self.tmp.name, "leads.db"),
            os.path.join(self.tmp.name, "leads.csv"),
        )
        self.score_store = ScoreStore(
            os.path.join(self.tmp.name, "scores.db"),
            os.path.join(self.tmp.name, "scores.csv"),
        )
        self.lead_store.add(
            [
                normalize_lead(
                    {"email": "jane@example.com", "name": "Jane", "company": "Example Inc"},
                    first_seen_at="2026-06-01T00:00:01+00:00",
                ),
                normalize_lead(
                    {"company": "Acme"},  # sparse -> low score
                    first_seen_at="2026-06-01T00:00:02+00:00",
                ),
            ]
        )

    def test_scores_every_lead_and_mirrors(self):
        count, scores = score_all(self.lead_store, self.score_store, RuleScorer())
        self.assertEqual(count, 2)
        self.assertEqual(self.score_store.count(), 2)
        # one score row per lead, keyed by dedup_key
        keys = {r["dedup_key"] for r in self.score_store.all()}
        self.assertEqual(keys, {l.dedup_key for l in self.lead_store.all()})
        # CSV mirror count matches SQLite truth
        self.assertEqual(len(self.score_store.read_csv()), 2)

    def test_deterministic_rescore_is_stable(self):
        score_all(self.lead_store, self.score_store, RuleScorer())
        first = self.score_store.all()
        score_all(self.lead_store, self.score_store, RuleScorer())
        self.assertEqual(self.score_store.count(), 2)
        self.assertEqual(
            [(r["dedup_key"], r["score"]) for r in first],
            [(r["dedup_key"], r["score"]) for r in self.score_store.all()],
        )


if __name__ == "__main__":
    unittest.main()

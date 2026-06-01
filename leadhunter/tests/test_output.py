"""Hermetic tests for the output package — consolidated qualified-leads join.

Covers the `QualifiedLead` record round-trip, the read-only `assemble_qualified`
join (identity preference, score attachment, sort, summary, optional stores), and
the dual-sink `QualifiedLeadStore` + `build_qualified_output` driver
(integrity, idempotency, rescore refresh, reopen). No network, no real LLM.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.enrichment import (
    DerivationEnricher,
    EnrichmentStore,
    enrich_and_persist,
)
from leadhunter.ingestion.model import Lead
from leadhunter.ingestion.persistence import LeadStore
from leadhunter.output import (
    QualifiedLead,
    QualifiedLeadStore,
    QualifiedSummary,
    assemble_qualified,
    build_qualified_output,
)
from leadhunter.scoring import RuleScorer, ScoreStore, score_all


class QualifiedLeadRecordTests(unittest.TestCase):
    def test_row_round_trip(self):
        q = QualifiedLead(
            dedup_key="email:ada@acme.com",
            name="Ada",
            email="ada@acme.com",
            domain="acme.com",
            score=75,
            tier="hot",
            reasons=("personal email (+30)", "domain (+20)"),
            score_method="rules",
            enrichment_method="derive",
            filled=("domain",),
        )
        back = QualifiedLead.from_row(q.to_row())
        self.assertEqual(back, q)
        # JSON-list columns serialize as lists.
        row = q.to_row()
        self.assertEqual(json.loads(row["reasons"]), list(q.reasons))
        self.assertEqual(json.loads(row["filled"]), ["domain"])
        self.assertEqual(row["score"], 75)

    def test_scored_and_enriched_flags(self):
        self.assertFalse(QualifiedLead().scored)
        self.assertFalse(QualifiedLead().enriched)
        self.assertTrue(QualifiedLead(score_method="rules").scored)
        self.assertTrue(QualifiedLead(filled=("domain",)).enriched)


class AssembleTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        self.leads = LeadStore(
            os.path.join(self.base, "leads.db"), os.path.join(self.base, "leads.csv")
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _enriched(self):
        return EnrichmentStore(
            os.path.join(self.base, "enr.db"), os.path.join(self.base, "enr.csv")
        )

    def _scores(self):
        return ScoreStore(
            os.path.join(self.base, "sc.db"), os.path.join(self.base, "sc.csv")
        )

    def test_base_only_falls_back_to_ingested_identity(self):
        self.leads.add([Lead(name="Solo", domain="solo.com", email="x@solo.com")])
        summary, qualified = assemble_qualified(self.leads)
        self.assertEqual(len(qualified), 1)
        q = qualified[0]
        self.assertEqual(q.domain, "solo.com")
        self.assertFalse(q.scored)        # no score store -> unscored
        self.assertFalse(q.enriched)      # no enrichment store
        self.assertEqual(q.score, 0)
        self.assertEqual(q.tier, "")
        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.scored, 0)
        self.assertEqual(summary.enriched, 0)

    def test_prefers_enriched_identity(self):
        # Ingested lead has no domain; enrichment derives it from the email.
        self.leads.add([Lead(name="Ada", email="ada@acme.com")])
        enriched = self._enriched()
        enrich_and_persist(self.leads, DerivationEnricher(), enriched)
        _, qualified = assemble_qualified(self.leads, enrichment_store=enriched)
        q = qualified[0]
        self.assertEqual(q.domain, "acme.com")          # filled by enrichment
        self.assertEqual(q.enrichment_method, "derive")
        self.assertEqual(q.filled, ("domain",))
        self.assertTrue(q.enriched)

    def test_attaches_score(self):
        self.leads.add([Lead(name="Ada", email="ada@acme.com", domain="acme.com")])
        scores = self._scores()
        score_all(self.leads, scores, RuleScorer())
        _, qualified = assemble_qualified(self.leads, score_store=scores)
        q = qualified[0]
        self.assertTrue(q.scored)
        self.assertEqual(q.score_method, "rules")
        self.assertGreater(q.score, 0)
        self.assertIn(q.tier, {"cold", "warm", "hot"})
        self.assertTrue(q.reasons)

    def test_sorted_by_score_desc(self):
        # Rich identity scores higher than a bare-name lead.
        self.leads.add(
            [
                Lead(name="Bare"),  # weakest
                Lead(
                    name="Ada",
                    company="Acme",
                    email="ada@acme.com",
                    domain="acme.com",
                    phone="+1 555 0100",
                    source_url="https://acme.com",
                ),  # strongest
            ]
        )
        scores = self._scores()
        score_all(self.leads, scores, RuleScorer())
        summary, qualified = assemble_qualified(self.leads, score_store=scores)
        self.assertEqual([q.name for q in qualified], ["Ada", "Bare"])
        self.assertGreaterEqual(qualified[0].score, qualified[1].score)
        self.assertEqual(summary.scored, 2)
        self.assertEqual(sum(summary.by_tier.values()), 2)


class QualifiedLeadStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = self._tmp.name
        self.db = os.path.join(base, "qual.db")
        self.csv = os.path.join(base, "qual.csv")
        self.store = QualifiedLeadStore(self.db, self.csv)

    def tearDown(self):
        self._tmp.cleanup()

    def _q(self, **kw):
        params = dict(dedup_key="email:ada@acme.com", name="Ada", email="ada@acme.com")
        params.update(kw)
        return QualifiedLead(**params)

    def test_csv_exists_before_first_write(self):
        self.assertEqual(self.store.read_csv(), [])
        self.assertEqual(self.store.count(), 0)

    def test_insert_and_dual_sink_integrity(self):
        q = self._q(domain="acme.com", score=50, tier="warm",
                    reasons=("personal email (+30)", "domain (+20)"),
                    score_method="rules", enrichment_method="derive", filled=("domain",))
        self.assertTrue(self.store.upsert(q))
        self.assertEqual(self.store.count(), 1)
        sql = self.store.all()[0]
        csv_row = self.store.read_csv()[0]
        self.assertEqual(sql, q)
        self.assertEqual(csv_row, q)   # CSV mirror == SQLite truth

    def test_overwrite_on_rescore(self):
        self.store.upsert(self._q(score=10, tier="cold", score_method="rules"))
        # Same key, higher score -> whole row refreshed.
        changed = self.store.upsert(self._q(score=80, tier="hot", score_method="rules"))
        self.assertTrue(changed)
        self.assertEqual(self.store.count(), 1)
        self.assertEqual(self.store.all()[0].score, 80)
        self.assertEqual(self.store.all()[0].tier, "hot")

    def test_idempotent_upsert(self):
        q = self._q(score=42, tier="warm", score_method="rules")
        self.assertTrue(self.store.upsert(q))
        self.assertFalse(self.store.upsert(q))  # identical -> no change
        self.assertEqual(self.store.count(), 1)

    def test_reopen_persists(self):
        self.store.upsert(self._q(domain="acme.com", score=50, score_method="rules"))
        reopened = QualifiedLeadStore(self.db, self.csv)
        self.assertEqual(reopened.count(), 1)
        self.assertEqual(reopened.all()[0].domain, "acme.com")


class BuildDriverTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = self._tmp.name
        self.leads = LeadStore(
            os.path.join(base, "leads.db"), os.path.join(base, "leads.csv")
        )
        self.leads.add(
            [
                Lead(
                    name="Ada", company="Acme", email="ada@acme.com",
                    phone="+1 555 0100", source_url="https://acme.com",
                ),  # strong, domain derivable from email
                Lead(name="Bare"),  # weak
            ]
        )
        self.enriched = EnrichmentStore(
            os.path.join(base, "enr.db"), os.path.join(base, "enr.csv")
        )
        self.scores = ScoreStore(
            os.path.join(base, "sc.db"), os.path.join(base, "sc.csv")
        )
        self.out = QualifiedLeadStore(
            os.path.join(base, "qual.db"), os.path.join(base, "qual.csv")
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_end_to_end_hottest_first(self):
        enrich_and_persist(self.leads, DerivationEnricher(), self.enriched)
        score_all(self.leads, self.scores, RuleScorer())
        summary, written = build_qualified_output(
            self.leads, self.out,
            enrichment_store=self.enriched, score_store=self.scores,
        )
        self.assertEqual(summary.total, 2)
        self.assertEqual(written, 2)
        self.assertEqual(self.out.count(), 2)
        rows = self.out.all()
        # Strong lead surfaces first, with the enrichment-derived domain present.
        self.assertEqual(rows[0].name, "Ada")
        self.assertEqual(rows[0].domain, "acme.com")
        self.assertTrue(rows[0].scored)
        self.assertTrue(rows[0].enriched)
        self.assertGreaterEqual(rows[0].score, rows[1].score)
        # M1 leads table untouched.
        self.assertEqual(self.leads.count(), 2)

    def test_build_is_idempotent(self):
        enrich_and_persist(self.leads, DerivationEnricher(), self.enriched)
        score_all(self.leads, self.scores, RuleScorer())
        build_qualified_output(
            self.leads, self.out,
            enrichment_store=self.enriched, score_store=self.scores,
        )
        _, written_again = build_qualified_output(
            self.leads, self.out,
            enrichment_store=self.enriched, score_store=self.scores,
        )
        self.assertEqual(written_again, 0)
        self.assertEqual(self.out.count(), 2)

    def test_build_without_optional_stores(self):
        # Identity-only output: no enrichment, no scoring.
        summary, written = build_qualified_output(self.leads, self.out)
        self.assertEqual(written, 2)
        self.assertEqual(summary.scored, 0)
        self.assertEqual(summary.enriched, 0)
        for q in self.out.all():
            self.assertFalse(q.scored)
            self.assertFalse(q.enriched)

    def test_rebuild_after_rescore_refreshes_output(self):
        # Build once with no scores (cold), then attach scores and rebuild.
        build_qualified_output(self.leads, self.out)
        self.assertEqual(self.out.all()[0].score, 0)
        score_all(self.leads, self.scores, RuleScorer())
        _, written = build_qualified_output(
            self.leads, self.out, score_store=self.scores
        )
        self.assertEqual(written, 2)  # both rows refreshed with their scores
        self.assertTrue(all(q.scored for q in self.out.all()))


if __name__ == "__main__":
    unittest.main()

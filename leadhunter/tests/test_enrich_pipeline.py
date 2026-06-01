"""Hermetic tests for enrich_all — driver, opt-in gate, store left untouched."""

import os
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.enrichment import (
    DerivationEnricher,
    EnrichmentNetworkNotAllowedError,
    EnrichResult,
    IdentityEnricher,
    enrich_all,
)
from leadhunter.ingestion.model import Lead
from leadhunter.ingestion.persistence import LeadStore


class FakeNetworkEnricher(IdentityEnricher):
    """A no-op enricher that merely declares it needs network (for gating)."""

    name = "fake-net"
    requires_network = True

    def enrich(self, lead):  # pragma: no cover - never called when fail-closed
        return EnrichResult(lead=lead, filled=(), method=self.name)


class EnrichPipelineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = self._tmp.name
        self.store = LeadStore(
            os.path.join(base, "leads.db"), os.path.join(base, "leads.csv")
        )
        self.store.add(
            [
                Lead(name="Ada", email="ada@acme.com"),          # domain derivable
                Lead(company="Beta", source_url="https://beta.io"),  # from url
                Lead(name="Solo", domain="solo.com", email="x@solo.com"),  # no change
            ]
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_returns_results_and_summary(self):
        summary, results = enrich_all(self.store, DerivationEnricher())
        self.assertEqual(summary.processed, 3)
        self.assertEqual(summary.changed, 2)
        self.assertEqual(summary.filled_by_field, {"domain": 2})
        self.assertEqual(len(results), 3)
        self.assertTrue(all(isinstance(r, EnrichResult) for r in results))
        derived = {r.lead.domain for r in results if r.changed}
        self.assertEqual(derived, {"acme.com", "beta.io"})

    def test_store_left_unmodified(self):
        before = {l.dedup_key: l.to_row() for l in self.store.all()}
        enrich_all(self.store, DerivationEnricher())
        after = {l.dedup_key: l.to_row() for l in self.store.all()}
        self.assertEqual(self.store.count(), 3)
        self.assertEqual(before, after)  # no write-back this slice

    def test_idempotent_second_pass(self):
        # The store is untouched, so a second pass reports identical changes.
        s1, _ = enrich_all(self.store, DerivationEnricher())
        s2, _ = enrich_all(self.store, DerivationEnricher())
        self.assertEqual(s1.changed, s2.changed)
        self.assertEqual(s1.filled_by_field, s2.filled_by_field)

    def test_network_enricher_refused_when_not_allowed(self):
        with self.assertRaises(EnrichmentNetworkNotAllowedError):
            enrich_all(self.store, FakeNetworkEnricher())

    def test_network_enricher_allowed_with_opt_in(self):
        summary, results = enrich_all(
            self.store, FakeNetworkEnricher(), allow_network=True
        )
        self.assertEqual(summary.processed, 3)
        self.assertEqual(summary.changed, 0)

    def test_empty_store(self):
        base = tempfile.mkdtemp()
        empty = LeadStore(
            os.path.join(base, "e.db"), os.path.join(base, "e.csv")
        )
        summary, results = enrich_all(empty, DerivationEnricher())
        self.assertEqual(summary.processed, 0)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()

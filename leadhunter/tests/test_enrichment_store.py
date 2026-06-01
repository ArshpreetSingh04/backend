"""Hermetic tests for EnrichmentStore — dual-sink persistence + fill-only upsert."""

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
    EnrichmentNetworkNotAllowedError,
    EnrichmentStore,
    EnrichResult,
    IdentityEnricher,
    enrich_all,
    enrich_and_persist,
    persist_enrichments,
)
from leadhunter.ingestion.model import Lead
from leadhunter.ingestion.persistence import LeadStore


class FakeNetworkEnricher(IdentityEnricher):
    """No-op enricher that merely declares it needs network (for gating)."""

    name = "fake-net"
    requires_network = True

    def enrich(self, lead):  # pragma: no cover - never called when fail-closed
        return EnrichResult(lead=lead, filled=(), method=self.name)


class EnrichmentStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = self._tmp.name
        self.db = os.path.join(base, "enriched.db")
        self.csv = os.path.join(base, "enriched.csv")
        self.store = EnrichmentStore(self.db, self.csv)

    def tearDown(self):
        self._tmp.cleanup()

    def _result(self, lead, filled=(), method="derive"):
        return EnrichResult(lead=lead, filled=tuple(filled), method=method)

    def test_csv_exists_before_first_write(self):
        # Header-only mirror created at construction.
        rows = self.store.read_csv()
        self.assertEqual(rows, [])
        self.assertEqual(self.store.count(), 0)

    def test_insert_changed_result(self):
        lead = Lead(name="Ada", email="ada@acme.com", domain="acme.com")
        changed = self.store.upsert(self._result(lead, filled=("domain",)))
        self.assertTrue(changed)
        self.assertEqual(self.store.count(), 1)
        stored_lead, meta = self.store.all()[0]
        self.assertEqual(stored_lead.dedup_key, lead.dedup_key)
        self.assertEqual(stored_lead.domain, "acme.com")
        self.assertEqual(meta["filled"], ["domain"])
        self.assertEqual(meta["method"], "derive")
        self.assertTrue(meta["enriched_at"])

    def test_dual_sink_integrity(self):
        lead = Lead(name="Ada", email="ada@acme.com", domain="acme.com")
        self.store.upsert(self._result(lead, filled=("domain",)))
        sql_lead, sql_meta = self.store.all()[0]
        csv_row = self.store.read_csv()[0]
        self.assertEqual(csv_row["dedup_key"], sql_lead.dedup_key)
        self.assertEqual(csv_row["domain"], sql_lead.domain)
        self.assertEqual(csv_row["method"], sql_meta["method"])
        self.assertEqual(json.loads(csv_row["filled"]), sql_meta["filled"])
        self.assertEqual(csv_row["enriched_at"], sql_meta["enriched_at"])

    def test_idempotent_second_pass(self):
        lead = Lead(name="Ada", email="ada@acme.com", domain="acme.com")
        r = self._result(lead, filled=("domain",), method="derive")
        self.assertTrue(self.store.upsert(r, enriched_at="2026-06-01T00:00:00+00:00"))
        # Same result again -> no change reported, contents stable.
        self.assertFalse(self.store.upsert(r, enriched_at="2026-06-01T09:00:00+00:00"))
        self.assertEqual(self.store.count(), 1)
        _, meta = self.store.all()[0]
        self.assertEqual(meta["enriched_at"], "2026-06-01T00:00:00+00:00")

    def test_fill_only_never_overwrites(self):
        key = Lead(email="ada@acme.com").dedup_key
        # First: a lead with no company/phone.
        first = Lead(email="ada@acme.com", domain="acme.com", dedup_key=key)
        self.store.upsert(self._result(first, filled=("domain",)))
        # Second (same key): fills empty company, but tries to change domain too.
        second = Lead(
            email="ada@acme.com",
            domain="OTHER.com",      # must NOT overwrite the existing non-empty value
            company="Acme",          # empty before -> should be filled
            dedup_key=key,
        )
        changed = self.store.upsert(self._result(second, filled=("company",)))
        self.assertTrue(changed)
        stored_lead, meta = self.store.all()[0]
        self.assertEqual(self.store.count(), 1)
        self.assertEqual(stored_lead.domain, "acme.com")   # preserved
        self.assertEqual(stored_lead.company, "Acme")        # filled
        self.assertEqual(meta["filled"], ["company", "domain"])  # unioned, sorted

    def test_dedup_key_is_primary_key(self):
        key = "email:dup@x.com"
        a = Lead(email="dup@x.com", name="A", dedup_key=key)
        b = Lead(email="dup@x.com", name="B-ignored", dedup_key=key)
        self.store.upsert(self._result(a))
        self.store.upsert(self._result(b))
        self.assertEqual(self.store.count(), 1)
        stored_lead, _ = self.store.all()[0]
        self.assertEqual(stored_lead.name, "A")  # name already set; not overwritten

    def test_unchanged_result_still_persists_snapshot(self):
        lead = Lead(name="Solo", domain="solo.com", email="x@solo.com")
        changed = self.store.upsert(self._result(lead, filled=()))
        self.assertTrue(changed)  # first insert is a change
        self.assertEqual(self.store.count(), 1)
        stored_lead, meta = self.store.all()[0]
        self.assertEqual(stored_lead.domain, "solo.com")
        self.assertEqual(meta["filled"], [])

    def test_reopen_persists(self):
        lead = Lead(name="Ada", email="ada@acme.com", domain="acme.com")
        self.store.upsert(self._result(lead, filled=("domain",)))
        reopened = EnrichmentStore(self.db, self.csv)
        self.assertEqual(reopened.count(), 1)
        stored_lead, _ = reopened.all()[0]
        self.assertEqual(stored_lead.domain, "acme.com")


class PersistEnrichmentsDriverTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = self._tmp.name
        self.leads = LeadStore(
            os.path.join(base, "leads.db"), os.path.join(base, "leads.csv")
        )
        self.leads.add(
            [
                Lead(name="Ada", email="ada@acme.com"),               # domain derivable
                Lead(company="Beta", source_url="https://beta.io"),   # from url
                Lead(name="Solo", domain="solo.com", email="x@solo.com"),  # no change
            ]
        )
        self.enriched = EnrichmentStore(
            os.path.join(base, "enriched.db"), os.path.join(base, "enriched.csv")
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_persist_enrichments_end_to_end(self):
        _, results = enrich_all(self.leads, DerivationEnricher())
        persisted = persist_enrichments(results, self.enriched)
        self.assertEqual(persisted, 3)  # all three first-inserted
        self.assertEqual(self.enriched.count(), 3)
        domains = {l.domain for l, _ in self.enriched.all()}
        self.assertEqual(domains, {"acme.com", "beta.io", "solo.com"})
        # M1 leads table untouched.
        self.assertEqual(self.leads.count(), 3)

    def test_persist_is_idempotent(self):
        _, results = enrich_all(self.leads, DerivationEnricher())
        persist_enrichments(results, self.enriched)
        # Second pass over identical results -> nothing changes.
        again = persist_enrichments(results, self.enriched)
        self.assertEqual(again, 0)
        self.assertEqual(self.enriched.count(), 3)

    def test_enrich_and_persist_convenience(self):
        processed, persisted = enrich_and_persist(
            self.leads, DerivationEnricher(), self.enriched
        )
        self.assertEqual(processed, 3)
        self.assertEqual(persisted, 3)
        self.assertEqual(self.enriched.count(), 3)

    def test_enrich_and_persist_network_refused(self):
        with self.assertRaises(EnrichmentNetworkNotAllowedError):
            enrich_and_persist(self.leads, FakeNetworkEnricher(), self.enriched)
        self.assertEqual(self.enriched.count(), 0)

    def test_enrich_and_persist_network_allowed(self):
        processed, persisted = enrich_and_persist(
            self.leads, FakeNetworkEnricher(), self.enriched, allow_network=True
        )
        self.assertEqual(processed, 3)
        # Fake enricher fills nothing, but each lead snapshot is first-inserted.
        self.assertEqual(persisted, 3)
        self.assertEqual(self.enriched.count(), 3)


if __name__ == "__main__":
    unittest.main()

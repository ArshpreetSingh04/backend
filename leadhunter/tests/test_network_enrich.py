"""Hermetic tests for the opt-in network WebContactEnricher.

Network is mocked: the `_http_get` seam (and robots check) is overridden so no
live HTTP ever happens. Covers parsing, fill-only/no-overwrite, dedup_key
preservation, the short-circuit (no fetch when nothing to fill), robots refusal,
polite delay, the pipeline opt-in gate, and end-to-end dual-sink persistence.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.enrichment import (
    EnrichmentNetworkNotAllowedError,
    EnrichmentStore,
    RobotsDisallowedError,
    WebContactEnricher,
    enrich_all,
    enrich_and_persist,
)
from leadhunter.ingestion.model import Lead
from leadhunter.ingestion.persistence import LeadStore

PAGE = (
    "<html><body>Contact us: "
    '<a href="mailto:Sales@Acme.com">email</a> '
    '<a href="tel:+1-555-0100">call</a>'
    "</body></html>"
)


def make_enricher(page="", *, robots_ok=True, calls=None, sleeps=None):
    """A WebContactEnricher with its network seam replaced by canned fixtures."""
    enr = WebContactEnricher(
        delay=0.5,
        sleep=(sleeps.append if sleeps is not None else (lambda s: None)),
    )

    def fake_get(url):
        if calls is not None:
            calls.append(url)
        if url.endswith("/robots.txt"):
            return (
                "User-agent: *\nDisallow: /\n"
                if not robots_ok
                else "User-agent: *\nDisallow:\n"
            )
        return page

    enr._http_get = fake_get  # type: ignore[assignment]
    return enr


class WebContactEnricherTests(unittest.TestCase):
    def test_fills_email_and_phone_from_own_site(self):
        enr = make_enricher(PAGE)
        result = enr.enrich(Lead(company="Acme", domain="acme.com"))
        self.assertEqual(result.filled, ("email", "phone"))
        self.assertEqual(result.lead.email, "sales@acme.com")  # casefolded
        self.assertEqual(result.lead.phone, "+1-555-0100")
        self.assertTrue(result.changed)
        self.assertEqual(result.method, "web_contact")

    def test_does_not_overwrite_existing_fields(self):
        enr = make_enricher(PAGE)
        lead = Lead(company="Acme", domain="acme.com", email="known@acme.com")
        result = enr.enrich(lead)
        self.assertEqual(result.filled, ("phone",))  # only the empty field
        self.assertEqual(result.lead.email, "known@acme.com")  # untouched
        self.assertEqual(result.lead.phone, "+1-555-0100")

    def test_no_fetch_when_nothing_to_fill(self):
        calls = []
        enr = make_enricher(PAGE, calls=calls)
        lead = Lead(domain="acme.com", email="a@acme.com", phone="+1-555-0100")
        result = enr.enrich(lead)
        self.assertFalse(result.changed)
        self.assertEqual(result.lead, lead)
        self.assertEqual(calls, [])  # short-circuit: zero network calls

    def test_no_fetch_when_no_target_url(self):
        calls = []
        enr = make_enricher(PAGE, calls=calls)
        result = enr.enrich(Lead(company="NoSite"))  # no domain/source_url
        self.assertFalse(result.changed)
        self.assertEqual(calls, [])

    def test_plain_text_email_fallback_when_no_mailto(self):
        enr = make_enricher("Reach the team at hello@beta.io for details.")
        result = enr.enrich(Lead(domain="beta.io"))
        self.assertEqual(result.lead.email, "hello@beta.io")

    def test_dedup_key_preserved_when_email_filled(self):
        enr = make_enricher(PAGE)
        lead = Lead(company="Acme", domain="acme.com")
        original_key = lead.dedup_key
        result = enr.enrich(lead)
        self.assertEqual(result.lead.dedup_key, original_key)  # not re-keyed

    def test_prefers_source_url_over_domain(self):
        calls = []
        enr = make_enricher(PAGE, calls=calls)
        enr.enrich(Lead(domain="acme.com", source_url="https://acme.com/contact"))
        fetched = [u for u in calls if not u.endswith("/robots.txt")]
        self.assertEqual(fetched, ["https://acme.com/contact"])

    def test_robots_disallow_raises(self):
        enr = make_enricher(PAGE, robots_ok=False)
        with self.assertRaises(RobotsDisallowedError):
            enr.enrich(Lead(domain="acme.com"))

    def test_polite_delay_invoked_before_fetch(self):
        sleeps = []
        enr = make_enricher(PAGE, sleeps=sleeps)
        enr.enrich(Lead(domain="acme.com"))
        self.assertIn(0.5, sleeps)

    def test_no_match_returns_unchanged(self):
        enr = make_enricher("<html><body>No contact details here.</body></html>")
        lead = Lead(company="Acme", domain="acme.com")
        result = enr.enrich(lead)
        self.assertFalse(result.changed)
        self.assertEqual(result.lead, lead)


class WebContactPipelineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        self.store = LeadStore(
            os.path.join(self.base, "leads.db"), os.path.join(self.base, "leads.csv")
        )
        self.store.add([Lead(company="Acme", domain="acme.com")])

    def tearDown(self):
        self._tmp.cleanup()

    def test_refused_without_opt_in(self):
        with self.assertRaises(EnrichmentNetworkNotAllowedError):
            enrich_all(self.store, make_enricher(PAGE))

    def test_runs_with_opt_in(self):
        summary, results = enrich_all(
            self.store, make_enricher(PAGE), allow_network=True
        )
        self.assertEqual(summary.processed, 1)
        self.assertEqual(summary.changed, 1)
        self.assertEqual(summary.filled_by_field, {"email": 1, "phone": 1})

    def test_enrich_and_persist_dual_sink_and_idempotent(self):
        estore = EnrichmentStore(
            os.path.join(self.base, "enr.db"), os.path.join(self.base, "enr.csv")
        )
        processed, persisted = enrich_and_persist(
            self.store, make_enricher(PAGE), estore, allow_network=True
        )
        self.assertEqual(processed, 1)
        self.assertEqual(persisted, 1)

        # Dual-sink integrity: CSV mirror == SQLite truth.
        import csv

        rows = [(lead.to_row(), meta) for lead, meta in estore.all()]
        self.assertEqual(len(rows), 1)
        lead_row, _meta = rows[0]
        self.assertEqual(lead_row["email"], "sales@acme.com")
        self.assertEqual(lead_row["phone"], "+1-555-0100")
        with open(os.path.join(self.base, "enr.csv"), newline="") as fh:
            csv_rows = list(csv.DictReader(fh))
        self.assertEqual(len(csv_rows), 1)
        self.assertEqual(csv_rows[0]["email"], "sales@acme.com")

        # Idempotent re-persist: nothing new changes on a second pass.
        _p2, persisted2 = enrich_and_persist(
            self.store, make_enricher(PAGE), estore, allow_network=True
        )
        self.assertEqual(persisted2, 0)
        self.assertEqual(estore.count(), 1)


if __name__ == "__main__":
    unittest.main()

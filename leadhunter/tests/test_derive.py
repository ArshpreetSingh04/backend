"""Unit tests for the deterministic `DerivationEnricher` (no network)."""

import os
import sys
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.enrichment import DerivationEnricher
from leadhunter.ingestion.model import Lead


class DerivationEnricherTests(unittest.TestCase):
    def setUp(self):
        self.enricher = DerivationEnricher()

    def test_domain_from_email(self):
        lead = Lead(name="Ada", email="ada@Example.COM")
        result = self.enricher.enrich(lead)
        self.assertTrue(result.changed)
        self.assertEqual(result.filled, ("domain",))
        self.assertEqual(result.lead.domain, "example.com")
        self.assertEqual(result.method, "derive")

    def test_domain_from_source_url_when_no_email(self):
        lead = Lead(company="Acme", source_url="https://www.Acme.io/team?x=1")
        result = self.enricher.enrich(lead)
        self.assertTrue(result.changed)
        self.assertEqual(result.lead.domain, "acme.io")

    def test_source_url_scheme_optional(self):
        lead = Lead(company="Acme", source_url="acme.io/contact")
        result = self.enricher.enrich(lead)
        self.assertEqual(result.lead.domain, "acme.io")

    def test_email_preferred_over_source_url(self):
        lead = Lead(email="ada@fromemail.com", source_url="https://fromurl.com")
        result = self.enricher.enrich(lead)
        self.assertEqual(result.lead.domain, "fromemail.com")

    def test_existing_domain_not_overwritten(self):
        lead = Lead(domain="keep.com", email="ada@other.com")
        result = self.enricher.enrich(lead)
        self.assertFalse(result.changed)
        self.assertEqual(result.filled, ())
        self.assertIs(result.lead, lead)
        self.assertEqual(result.lead.domain, "keep.com")

    def test_other_fields_untouched(self):
        lead = Lead(name="Ada", company="Acme", phone="123", email="ada@acme.com")
        result = self.enricher.enrich(lead)
        self.assertEqual(result.lead.name, "Ada")
        self.assertEqual(result.lead.company, "Acme")
        self.assertEqual(result.lead.phone, "123")
        self.assertEqual(result.lead.email, "ada@acme.com")

    def test_dedup_key_preserved(self):
        lead = Lead(name="Ada", email="ada@acme.com")
        original_key = lead.dedup_key
        result = self.enricher.enrich(lead)
        self.assertEqual(result.lead.dedup_key, original_key)

    def test_nothing_to_fill_returns_same_lead(self):
        lead = Lead(name="Ada", company="Acme")  # no email, no source_url
        result = self.enricher.enrich(lead)
        self.assertFalse(result.changed)
        self.assertIs(result.lead, lead)

    def test_deterministic(self):
        lead = Lead(email="ada@acme.com")
        a = self.enricher.enrich(lead)
        b = self.enricher.enrich(lead)
        self.assertEqual(a.lead.domain, b.lead.domain)
        self.assertEqual(a.filled, b.filled)

    def test_no_network_required(self):
        self.assertFalse(DerivationEnricher.requires_network)


if __name__ == "__main__":
    unittest.main()

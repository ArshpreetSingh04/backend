import os
import sys
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.ingestion.normalize import normalize_lead, dedup


class NormalizeLeadTest(unittest.TestCase):
    def test_trims_and_lowercases_email(self):
        lead = normalize_lead({"email": "  Jane@Example.COM "})
        self.assertEqual(lead.email, "jane@example.com")

    def test_derives_domain_from_email(self):
        lead = normalize_lead({"email": "a@foo.io"})
        self.assertEqual(lead.domain, "foo.io")

    def test_explicit_domain_preferred(self):
        lead = normalize_lead({"email": "a@foo.io", "domain": "Bar.IO"})
        self.assertEqual(lead.domain, "bar.io")

    def test_missing_fields_become_empty(self):
        lead = normalize_lead({"name": "Jane"})
        self.assertEqual(lead.company, "")
        self.assertEqual(lead.email, "")
        self.assertEqual(lead.phone, "")

    def test_raw_payload_preserved(self):
        raw = {"name": "Jane", "extra": "keep me"}
        lead = normalize_lead(raw)
        self.assertEqual(lead.raw["extra"], "keep me")

    def test_first_seen_at_injectable(self):
        lead = normalize_lead({"name": "x"}, first_seen_at="2026-06-01T00:00:00+00:00")
        self.assertEqual(lead.first_seen_at, "2026-06-01T00:00:00+00:00")


class DedupListTest(unittest.TestCase):
    def test_collapses_case_and_whitespace_duplicates(self):
        leads = [
            normalize_lead({"email": "jane@example.com", "name": "Jane"}),
            normalize_lead({"email": "  JANE@EXAMPLE.COM ", "name": "Jane D"}),
            normalize_lead({"email": "bob@example.com", "name": "Bob"}),
        ]
        result = dedup(leads)
        self.assertEqual(len(result), 2)

    def test_preserves_first_seen_order_and_first_value(self):
        leads = [
            normalize_lead({"email": "jane@example.com", "name": "First"}),
            normalize_lead({"email": "jane@example.com", "name": "Second"}),
        ]
        result = dedup(leads)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "First")

    def test_company_domain_duplicates_collapse(self):
        leads = [
            normalize_lead({"domain": "x.io", "company": "Widgets Inc"}),
            normalize_lead({"domain": "x.io", "company": "Widgets, LLC"}),
        ]
        # Different suffixes but same normalized domain+company -> 1 lead.
        result = dedup(leads)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()

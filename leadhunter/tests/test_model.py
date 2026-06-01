import os
import sys
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.ingestion.model import (
    Lead,
    compute_dedup_key,
    normalize_company,
)


class DedupKeyPrecedenceTest(unittest.TestCase):
    def test_email_wins(self):
        key = compute_dedup_key(
            email="Jane@Example.COM",
            domain="example.com",
            company="Example Inc",
            name="Jane Doe",
        )
        self.assertEqual(key, "email:jane@example.com")

    def test_domain_plus_company_when_no_email(self):
        key = compute_dedup_key(
            email="",
            domain="Example.com",
            company="Example, Inc.",
            name="Jane Doe",
        )
        self.assertEqual(key, "domain+company:example.com|example")

    def test_company_plus_name_when_no_email_or_domain(self):
        key = compute_dedup_key(
            email="", domain="", company="Acme LLC", name="John  Smith"
        )
        self.assertEqual(key, "company+name:acme|john smith")

    def test_hash_fallback_when_nothing_identifying(self):
        key = compute_dedup_key(email="", domain="", company="", name="")
        self.assertTrue(key.startswith("hash:"))
        self.assertEqual(len(key), len("hash:") + 40)

    def test_precedence_is_layered(self):
        # Same domain+company but different (missing) email must still
        # only fall through to the domain+company layer.
        a = compute_dedup_key("", "x.io", "Widgets Corp", "A")
        b = compute_dedup_key("", "x.io", "Widgets Corporation", "B")
        self.assertEqual(a, b)


class CompanySuffixTest(unittest.TestCase):
    def test_strips_common_suffixes(self):
        self.assertEqual(normalize_company("Example Inc"), "example")
        self.assertEqual(normalize_company("Example, LLC"), "example")
        self.assertEqual(normalize_company("Big Bank Corporation"), "big bank")
        self.assertEqual(normalize_company("Foo Ltd."), "foo")

    def test_collapses_whitespace_and_case(self):
        self.assertEqual(normalize_company("  ACME   Widgets  "), "acme widgets")

    def test_empty(self):
        self.assertEqual(normalize_company(None), "")
        self.assertEqual(normalize_company("   "), "")


class RowRoundTripTest(unittest.TestCase):
    def test_to_row_and_from_row(self):
        lead = Lead(
            name="Jane Doe",
            company="Example Inc",
            email="jane@example.com",
            domain="example.com",
            phone="+1 555 0100",
            source="manual",
            source_url="https://example.com/jane",
            raw={"b": 2, "a": 1},
            first_seen_at="2026-06-01T00:00:00+00:00",
        )
        row = lead.to_row()
        self.assertEqual(set(row.keys()), set(Lead.COLUMNS))
        self.assertIsInstance(row["raw"], str)

        restored = Lead.from_row(row)
        self.assertEqual(restored.name, lead.name)
        self.assertEqual(restored.email, lead.email)
        self.assertEqual(restored.dedup_key, lead.dedup_key)
        self.assertEqual(restored.raw, {"a": 1, "b": 2})

    def test_dedup_key_autocomputed(self):
        lead = Lead(email="x@Y.com")
        self.assertEqual(lead.dedup_key, "email:x@y.com")


if __name__ == "__main__":
    unittest.main()

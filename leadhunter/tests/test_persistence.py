import os
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.ingestion.normalize import normalize_lead
from leadhunter.ingestion.persistence import LeadStore


def _sample_leads():
    return [
        normalize_lead(
            {"email": "jane@example.com", "name": "Jane", "company": "Example Inc"},
            first_seen_at="2026-06-01T00:00:01+00:00",
        ),
        normalize_lead(
            {"email": "bob@acme.io", "name": "Bob", "company": "Acme"},
            first_seen_at="2026-06-01T00:00:02+00:00",
        ),
    ]


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "leads.db")
        self.csv = os.path.join(self.tmp.name, "leads.csv")

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_to_both_sinks_with_equal_content(self):
        store = LeadStore(self.db, self.csv)
        inserted = store.add(_sample_leads())
        self.assertEqual(inserted, 2)

        db_leads = store.all()
        csv_leads = store.read_csv()
        self.assertEqual(len(db_leads), 2)
        self.assertEqual(len(csv_leads), 2)

        # Both sinks hold the identical set of leads.
        db_keys = {l.dedup_key for l in db_leads}
        csv_keys = {l.dedup_key for l in csv_leads}
        self.assertEqual(db_keys, csv_keys)
        for a, b in zip(db_leads, csv_leads):
            self.assertEqual(a.to_row(), b.to_row())

    def test_reingest_is_idempotent_in_both_sinks(self):
        store = LeadStore(self.db, self.csv)
        store.add(_sample_leads())
        inserted_again = store.add(_sample_leads())
        self.assertEqual(inserted_again, 0)
        self.assertEqual(store.count(), 2)
        self.assertEqual(len(store.read_csv()), 2)

    def test_csv_is_derived_mirror_of_db(self):
        store = LeadStore(self.db, self.csv)
        store.add(_sample_leads())
        # A fresh store over the same DB regenerates the CSV from SQLite.
        store2 = LeadStore(self.db, self.csv)
        self.assertEqual(
            {l.dedup_key for l in store2.all()},
            {l.dedup_key for l in store2.read_csv()},
        )

    def test_csv_mirror_exists_before_first_write(self):
        LeadStore(self.db, self.csv)
        self.assertTrue(os.path.exists(self.csv))
        # Header-only CSV (no leads yet).
        store = LeadStore(self.db, self.csv)
        self.assertEqual(store.read_csv(), [])

    def test_roundtrip_preserves_raw_payload(self):
        store = LeadStore(self.db, self.csv)
        store.add(
            [normalize_lead({"email": "z@z.io", "name": "Z", "extra": "payload"})]
        )
        restored = store.all()[0]
        self.assertEqual(restored.raw.get("extra"), "payload")


if __name__ == "__main__":
    unittest.main()

import json
import os
import sys
import tempfile
import unittest
from typing import Any, Iterator, Mapping

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.ingestion.pipeline import ingest, IngestResult
from leadhunter.ingestion.persistence import LeadStore
from leadhunter.ingestion.sources.base import Source, NetworkNotAllowedError
from leadhunter.ingestion.sources.file_source import FileSource


class _ListSource(Source):
    """In-memory source for tests; network flag is configurable."""

    def __init__(self, records, *, name="list", requires_network=False):
        self._records = list(records)
        self.name = name
        self.requires_network = requires_network

    def records(self) -> Iterator[Mapping[str, Any]]:
        yield from self._records


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = os.path.join(self.tmp.name, "leads.db")
        self.csv = os.path.join(self.tmp.name, "leads.csv")
        self.store = LeadStore(self.db, self.csv)

    def _write(self, name, text):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_end_to_end_from_file(self):
        path = self._write(
            "leads.json",
            json.dumps(
                [
                    {"email": "jane@example.com", "company": "Example Inc"},
                    {"email": "john@acme.io", "company": "Acme"},
                ]
            ),
        )
        result = ingest([FileSource(path)], self.store)
        self.assertIsInstance(result, IngestResult)
        self.assertEqual(result.read, 2)
        self.assertEqual(result.after_dedup, 2)
        self.assertEqual(result.inserted, 2)
        self.assertEqual(self.store.count(), 2)

    def test_dual_sink_integrity_csv_matches_sqlite(self):
        """After ingest, the CSV mirror rows must exactly match SQLite rows."""
        path = self._write(
            "leads.jsonl",
            '{"email": "a@x.com", "company": "Alpha"}\n'
            '{"email": "b@y.com", "company": "Beta"}\n'
            '{"name": "No Email", "company": "Gamma Corp", "domain": "gamma.com"}\n',
        )
        ingest([FileSource(path)], self.store)

        sqlite_rows = [lead.to_row() for lead in self.store.all()]
        csv_rows = [lead.to_row() for lead in self.store.read_csv()]
        self.assertEqual(sqlite_rows, csv_rows)
        self.assertGreater(len(sqlite_rows), 0)

    def test_idempotent_second_run_inserts_zero(self):
        path = self._write(
            "leads.json",
            json.dumps([{"email": "jane@example.com", "company": "Example"}]),
        )
        first = ingest([FileSource(path)], self.store)
        second = ingest([FileSource(path)], self.store)
        self.assertEqual(first.inserted, 1)
        self.assertEqual(second.inserted, 0)
        self.assertEqual(self.store.count(), 1)

    def test_intra_batch_dedup(self):
        # Same email twice (different casing) collapses to one lead.
        src = _ListSource(
            [
                {"email": "Jane@Example.com", "company": "Example Inc"},
                {"email": "jane@example.com", "company": "Example"},
            ]
        )
        result = ingest([src], self.store)
        self.assertEqual(result.read, 2)
        self.assertEqual(result.after_dedup, 1)
        self.assertEqual(result.inserted, 1)
        self.assertEqual(self.store.count(), 1)

    def test_network_guard_refuses_without_optin(self):
        src = _ListSource([{"email": "x@y.com"}], requires_network=True, name="scraper")
        with self.assertRaises(NetworkNotAllowedError):
            ingest([src], self.store)
        # Nothing persisted because the guard fired before store.add.
        self.assertEqual(self.store.count(), 0)

    def test_network_guard_allows_with_optin(self):
        src = _ListSource([{"email": "x@y.com"}], requires_network=True, name="scraper")
        result = ingest([src], self.store, allow_network=True)
        self.assertEqual(result.inserted, 1)
        self.assertEqual(self.store.count(), 1)

    def test_multiple_sources_combined_and_deduped(self):
        a = self._write("a.jsonl", '{"email": "a@x.com"}\n')
        b = self._write("b.jsonl", '{"email": "a@x.com"}\n{"email": "b@x.com"}\n')
        result = ingest([FileSource(a), FileSource(b)], self.store)
        self.assertEqual(result.read, 3)
        self.assertEqual(result.after_dedup, 2)
        self.assertEqual(result.inserted, 2)


if __name__ == "__main__":
    unittest.main()

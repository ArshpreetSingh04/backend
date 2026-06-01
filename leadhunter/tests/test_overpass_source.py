import json
import os
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.ingestion.pipeline import ingest
from leadhunter.ingestion.persistence import LeadStore
from leadhunter.ingestion.sources.base import NetworkNotAllowedError
from leadhunter.ingestion.sources.overpass_source import (
    OverpassSource,
    RobotsDisallowedError,
)


# A canned Overpass response: two real businesses + one junk element (no tags).
_OVERPASS_JSON = json.dumps(
    {
        "elements": [
            {
                "type": "node",
                "id": 1,
                "tags": {
                    "name": "Acme Coffee",
                    "website": "https://www.Acme.io/contact",
                    "phone": "+1 555 0100",
                    "email": "hi@acme.io",
                },
            },
            {
                "type": "way",
                "id": 2,
                "tags": {
                    "name": "Beta Bakery",
                    "contact:website": "beta-bakery.example",
                    "contact:phone": "+1 555 0200",
                },
            },
            {"type": "node", "id": 3, "tags": {"highway": "bus_stop"}},
        ]
    }
)

_ROBOTS_ALLOW_ALL = "User-agent: *\nDisallow:\n"
_ROBOTS_DISALLOW_ALL = "User-agent: *\nDisallow: /\n"


class _FakeOverpass(OverpassSource):
    """OverpassSource with the single network seam replaced by fixtures.

    No real HTTP ever happens. ``_http_get`` returns a canned robots.txt for a
    ``/robots.txt`` URL and the canned API JSON otherwise; calls are recorded.
    """

    def __init__(self, *args, robots_text=_ROBOTS_ALLOW_ALL, api_json=_OVERPASS_JSON, **kwargs):
        kwargs.setdefault("delay", 0)  # no real sleeping in tests
        super().__init__(*args, **kwargs)
        self._robots_text = robots_text
        self._api_json = api_json
        self.calls = []

    def _http_get(self, url, *, data=None):
        self.calls.append((url, data))
        if url.endswith("/robots.txt"):
            return self._robots_text
        return self._api_json


class OverpassSourceTest(unittest.TestCase):
    def test_requires_network_is_true(self):
        self.assertTrue(_FakeOverpass("q").requires_network)

    def test_no_network_at_construction(self):
        src = _FakeOverpass("q")
        # Constructing must not touch the network seam at all.
        self.assertEqual(src.calls, [])

    def test_maps_elements_to_payloads(self):
        rows = list(_FakeOverpass("q").records())
        # Junk element (no name/contact) is skipped at the source.
        self.assertEqual(len(rows), 2)
        first = rows[0]
        self.assertEqual(first["company"], "Acme Coffee")
        self.assertEqual(first["phone"], "+1 555 0100")
        self.assertEqual(first["email"], "hi@acme.io")
        self.assertEqual(first["source"], "overpass")
        self.assertEqual(first["source_url"], "https://www.openstreetmap.org/node/1")

    def test_website_to_domain(self):
        rows = list(_FakeOverpass("q").records())
        self.assertEqual(rows[0]["domain"], "acme.io")          # strips scheme/path/www
        self.assertEqual(rows[1]["domain"], "beta-bakery.example")  # bare host

    def test_skips_elements_without_identity(self):
        only_junk = json.dumps({"elements": [{"type": "node", "id": 9, "tags": {"x": "y"}}]})
        rows = list(_FakeOverpass("q", api_json=only_junk).records())
        self.assertEqual(rows, [])

    def test_robots_disallowed_raises_and_skips_api(self):
        src = _FakeOverpass("q", robots_text=_ROBOTS_DISALLOW_ALL)
        with self.assertRaises(RobotsDisallowedError):
            list(src.records())
        # robots.txt was fetched, but the API query never was.
        self.assertTrue(all(url.endswith("/robots.txt") for url, _ in src.calls))

    def test_robots_allowed_then_fetches_api(self):
        src = _FakeOverpass("q")
        list(src.records())
        urls = [url for url, _ in src.calls]
        self.assertTrue(any(u.endswith("/robots.txt") for u in urls))
        self.assertTrue(any(u == src.endpoint for u in urls))

    def test_robots_check_skipped_when_disabled(self):
        src = _FakeOverpass("q", check_robots=False)
        list(src.records())
        self.assertTrue(all(not url.endswith("/robots.txt") for url, _ in src.calls))

    def test_delay_is_respected(self):
        slept = []
        src = _FakeOverpass("q", delay=2.5, sleep=slept.append)
        list(src.records())
        self.assertIn(2.5, slept)

    def test_query_sent_as_post_body(self):
        src = _FakeOverpass("node[amenity=cafe];out;")
        list(src.records())
        api_calls = [(u, d) for u, d in src.calls if u == src.endpoint]
        self.assertEqual(len(api_calls), 1)
        self.assertEqual(api_calls[0][1], b"node[amenity=cafe];out;")


class OverpassPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = LeadStore(
            os.path.join(self.tmp.name, "leads.db"),
            os.path.join(self.tmp.name, "leads.csv"),
        )

    def test_refused_without_optin(self):
        with self.assertRaises(NetworkNotAllowedError):
            ingest([_FakeOverpass("q")], self.store)
        self.assertEqual(self.store.count(), 0)

    def test_ingest_with_optin_persists_and_mirrors(self):
        result = ingest([_FakeOverpass("q")], self.store, allow_network=True)
        self.assertEqual(result.read, 2)
        self.assertEqual(result.after_dedup, 2)
        self.assertEqual(result.inserted, 2)
        self.assertEqual(self.store.count(), 2)
        # Dual-sink integrity: CSV mirror exactly matches SQLite.
        sqlite_rows = [lead.to_row() for lead in self.store.all()]
        csv_rows = [lead.to_row() for lead in self.store.read_csv()]
        self.assertEqual(sqlite_rows, csv_rows)

    def test_idempotent_second_run(self):
        first = ingest([_FakeOverpass("q")], self.store, allow_network=True)
        second = ingest([_FakeOverpass("q")], self.store, allow_network=True)
        self.assertEqual(first.inserted, 2)
        self.assertEqual(second.inserted, 0)
        self.assertEqual(self.store.count(), 2)


if __name__ == "__main__":
    unittest.main()

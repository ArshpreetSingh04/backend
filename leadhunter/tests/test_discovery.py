"""Hermetic tests for M3 Increment 2 discovery — no network, no real I/O.

Covers the deterministic `RuleSourceDiscoverer` floor (pure plan -> ranked
candidates mapping) and the `discover_sources` driver, including the
fail-closed network opt-in gate exercised with an in-memory fake discoverer.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.planning.base import SearchPlan
from leadhunter.discovery.base import (
    OFFICIAL_API,
    STRUCTURED_DIRECTORY,
    WEB_SEARCH,
    CandidateSource,
    DiscoveryNetworkNotAllowedError,
    SourceDiscoverer,
)
from leadhunter.discovery.rules import RuleSourceDiscoverer
from leadhunter.discovery.pipeline import discover_sources


def _plan(
    *,
    vertical="dentist",
    location="Austin, Texas",
    required_fields=("email", "phone"),
    target_count=50,
) -> SearchPlan:
    return SearchPlan.make(
        vertical=vertical,
        location=location,
        required_fields=required_fields,
        target_count=target_count,
        raw_prompt="Find me 50 dentists in Austin, Texas with email and phone",
        method="rules",
    )


class FakeDiscoverer(SourceDiscoverer):
    """In-memory discoverer returning canned candidates; configurable net flag."""

    def __init__(self, candidates, *, requires_network=False, name="fake"):
        self._candidates = list(candidates)
        self.requires_network = requires_network
        self.name = name

    def discover(self, plan):
        return list(self._candidates)


class CandidateSourceTest(unittest.TestCase):
    def test_row_round_trip(self):
        c = CandidateSource.make(
            kind=OFFICIAL_API,
            name="OpenStreetMap Overpass",
            query="[out:json];node;out;",
            risk="low",
            requires_network=True,
            rationale="structured open data",
            rank=0,
        )
        back = CandidateSource.from_row(c.to_row())
        self.assertEqual(back, c)

    def test_make_rejects_unknown_vocab(self):
        with self.assertRaises(Exception):
            CandidateSource.make(kind="nonsense", name="x", query="y")
        with self.assertRaises(Exception):
            CandidateSource.make(kind=WEB_SEARCH, name="x", query="y", risk="extreme")

    def test_columns_match_row_keys(self):
        c = CandidateSource.make(kind=WEB_SEARCH, name="n", query="q", risk="high")
        self.assertEqual(set(c.to_row().keys()), set(CandidateSource.COLUMNS))


class RuleSourceDiscovererTest(unittest.TestCase):
    def setUp(self):
        self.discoverer = RuleSourceDiscoverer()

    def test_emits_overpass_official_api_from_plan(self):
        candidates = self.discoverer.discover(_plan())
        official = [c for c in candidates if c.kind == OFFICIAL_API]
        self.assertEqual(len(official), 1)
        ql = official[0].query
        # Built deterministically from vertical + location.
        self.assertIn('["amenity"="dentist"]', ql)
        self.assertIn('area["name"="Austin, Texas"]', ql)
        self.assertTrue(official[0].requires_network)

    def test_preference_ranking_official_then_structured_then_web(self):
        candidates = self.discoverer.discover(_plan())
        kinds_in_order = [c.kind for c in candidates]
        self.assertEqual(
            kinds_in_order, [OFFICIAL_API, STRUCTURED_DIRECTORY, WEB_SEARCH]
        )
        # rank mirrors the ordering.
        self.assertEqual([c.rank for c in candidates], [0, 1, 2])

    def test_web_search_query_composed_from_plan(self):
        candidates = self.discoverer.discover(_plan())
        web = next(c for c in candidates if c.kind == WEB_SEARCH)
        self.assertEqual(web.query, "dentist Austin, Texas email phone")

    def test_risky_web_candidate_tagged_and_never_first(self):
        candidates = self.discoverer.discover(_plan())
        web = next(c for c in candidates if c.kind == WEB_SEARCH)
        self.assertEqual(web.risk, "high")
        self.assertTrue(web.requires_network)
        self.assertNotEqual(candidates[0].kind, WEB_SEARCH)

    def test_deterministic_across_calls(self):
        plan = _plan()
        self.assertEqual(self.discoverer.discover(plan), self.discoverer.discover(plan))

    def test_blank_location_still_yields_candidates(self):
        candidates = self.discoverer.discover(_plan(location=""))
        self.assertTrue(candidates)
        # Unknown-but-present vertical with no location: area clause omitted.
        official = next(c for c in candidates if c.kind == OFFICIAL_API)
        self.assertNotIn("area[", official.query)

    def test_unknown_vertical_uses_name_match(self):
        candidates = RuleSourceDiscoverer().discover(_plan(vertical="florist"))
        official = next(c for c in candidates if c.kind == OFFICIAL_API)
        self.assertIn('["name"~"florist",i]', official.query)

    def test_discoverer_is_offline(self):
        self.assertFalse(RuleSourceDiscoverer().requires_network)


class DiscoverSourcesTest(unittest.TestCase):
    def test_default_offline_run(self):
        summary, candidates = discover_sources(_plan())
        self.assertEqual(summary.total, len(candidates))
        self.assertEqual(summary.by_kind[OFFICIAL_API], 1)
        self.assertEqual(summary.by_kind[WEB_SEARCH], 1)

    def test_merges_and_dedupes_across_discoverers(self):
        plan = _plan()
        base = RuleSourceDiscoverer().discover(plan)
        # One overlapping candidate (same kind+query) + one unique extra.
        overlap = base[0]
        extra = CandidateSource.make(
            kind=STRUCTURED_DIRECTORY,
            name="Another directory",
            query="something else entirely",
            risk="medium",
            requires_network=False,
        )
        fake = FakeDiscoverer([overlap, extra], requires_network=False)
        summary, candidates = discover_sources(plan, [RuleSourceDiscoverer(), fake])
        # The overlapping (kind, query) appears exactly once; the extra is added.
        self.assertEqual(summary.total, len(base) + 1)
        keys = [(c.kind, c.query) for c in candidates]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn((extra.kind, extra.query), keys)

    def test_network_discoverer_refused_without_optin(self):
        fake = FakeDiscoverer([], requires_network=True, name="netty")
        with self.assertRaises(DiscoveryNetworkNotAllowedError):
            discover_sources(_plan(), [fake])

    def test_network_discoverer_runs_with_optin(self):
        canned = CandidateSource.make(
            kind=WEB_SEARCH, name="live", query="live query", risk="high"
        )
        fake = FakeDiscoverer([canned], requires_network=True, name="netty")
        summary, candidates = discover_sources(_plan(), [fake], allow_network=True)
        self.assertEqual(summary.total, 1)
        self.assertEqual(candidates[0].query, "live query")

    def test_summary_counts_match_returned_list(self):
        _, candidates = discover_sources(_plan())
        by_kind = {}
        for c in candidates:
            by_kind[c.kind] = by_kind.get(c.kind, 0) + 1
        summary, _ = discover_sources(_plan())
        self.assertEqual(summary.by_kind, by_kind)


if __name__ == "__main__":
    unittest.main()

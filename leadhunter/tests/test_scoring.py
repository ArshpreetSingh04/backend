"""Hermetic tests for the M2 scorers — no network, no real LLM.

Covers the deterministic `RuleScorer` floor and the optional `LLMScorer`,
whose every degradation path must fall back to the baseline. The LLM is a
local `FakeProvider` implementing the `LLMProvider` interface.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.ingestion.model import Lead
from leadhunter.llm.base import LLMProvider, LLMUnavailableError
from leadhunter.scoring.base import Score, tier_for
from leadhunter.scoring.rules import RuleScorer
from leadhunter.scoring.llm_scorer import LLMScorer


class FakeProvider(LLMProvider):
    """In-memory LLM stand-in: returns a canned reply, never touches network."""

    name = "fake"

    def __init__(self, *, reply="", up=True, raises=None, allow_network=False):
        super().__init__(allow_network=allow_network)
        self._reply = reply
        self._up = up
        self._raises = raises
        self.calls = 0

    def available(self) -> bool:
        return self._up

    def generate(self, prompt, *, system=None, temperature=0.0, max_tokens=None):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._reply


class RuleScorerTests(unittest.TestCase):
    def setUp(self):
        self.scorer = RuleScorer()

    def test_empty_lead_is_cold_floor(self):
        score = self.scorer.score(Lead())
        self.assertEqual(score.value, 0)
        self.assertEqual(score.tier, "cold")
        self.assertEqual(score.method, "rules")
        self.assertTrue(score.reasons)  # always explains itself

    def test_full_lead_is_hot(self):
        lead = Lead(
            name="Jane Doe",
            company="Example",
            email="jane@example.com",
            domain="example.com",
            phone="+1 555 0100",
            source_url="https://example.com/team",
        )
        score = self.scorer.score(lead)
        self.assertEqual(score.tier, "hot")
        self.assertGreaterEqual(score.value, 67)

    def test_role_email_penalised_vs_personal(self):
        base = dict(company="Example", domain="example.com")
        personal = self.scorer.score(Lead(email="jane@example.com", **base))
        role = self.scorer.score(Lead(email="info@example.com", **base))
        self.assertGreater(personal.value, role.value)
        self.assertTrue(any("role" in r for r in role.reasons))

    def test_deterministic(self):
        lead = Lead(name="Jane", company="Example", email="jane@example.com")
        a = self.scorer.score(lead)
        b = self.scorer.score(lead)
        self.assertEqual(a, b)

    def test_score_is_clamped_and_tier_consistent(self):
        lead = Lead(
            name="Jane Doe",
            company="Example",
            email="jane@example.com",
            domain="example.com",
            phone="+1 555 0100",
            source_url="https://example.com",
        )
        score = self.scorer.score(lead)
        self.assertLessEqual(score.value, 100)
        self.assertGreaterEqual(score.value, 0)
        self.assertEqual(score.tier, tier_for(score.value))


class TierBoundaryTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(tier_for(0), "cold")
        self.assertEqual(tier_for(33), "cold")
        self.assertEqual(tier_for(34), "warm")
        self.assertEqual(tier_for(66), "warm")
        self.assertEqual(tier_for(67), "hot")
        self.assertEqual(tier_for(100), "hot")


class LLMScorerTests(unittest.TestCase):
    def setUp(self):
        self.baseline = RuleScorer()
        self.lead = Lead(name="Jane", company="Example", email="jane@example.com")

    def test_uses_llm_when_allowed_and_available(self):
        provider = FakeProvider(reply='{"score": 88, "reasons": ["great fit"]}')
        scorer = LLMScorer(self.baseline, provider, allow_network=True)
        score = scorer.score(self.lead)
        self.assertEqual(score.value, 88)
        self.assertEqual(score.tier, "hot")
        self.assertEqual(score.method, "llm:fake")
        self.assertIn("great fit", score.reasons)
        self.assertEqual(provider.calls, 1)

    def test_falls_back_when_network_not_allowed(self):
        provider = FakeProvider(reply='{"score": 88, "reasons": ["x"]}')
        scorer = LLMScorer(self.baseline, provider, allow_network=False)
        score = scorer.score(self.lead)
        self.assertEqual(score, self.baseline.score(self.lead))
        self.assertEqual(provider.calls, 0)  # provider never touched

    def test_falls_back_when_provider_none(self):
        scorer = LLMScorer(self.baseline, None, allow_network=True)
        self.assertEqual(scorer.score(self.lead), self.baseline.score(self.lead))

    def test_falls_back_when_unavailable(self):
        provider = FakeProvider(reply='{"score": 88}', up=False)
        scorer = LLMScorer(self.baseline, provider, allow_network=True)
        score = scorer.score(self.lead)
        self.assertEqual(score, self.baseline.score(self.lead))
        self.assertEqual(provider.calls, 0)

    def test_falls_back_on_malformed_json(self):
        provider = FakeProvider(reply="sorry, I cannot help with that")
        scorer = LLMScorer(self.baseline, provider, allow_network=True)
        score = scorer.score(self.lead)
        self.assertEqual(score, self.baseline.score(self.lead))
        self.assertEqual(provider.calls, 1)  # tried, then fell back

    def test_falls_back_on_llm_error(self):
        provider = FakeProvider(raises=LLMUnavailableError("down"))
        scorer = LLMScorer(self.baseline, provider, allow_network=True)
        score = scorer.score(self.lead)
        self.assertEqual(score, self.baseline.score(self.lead))

    def test_llm_score_clamped(self):
        provider = FakeProvider(reply='{"score": 250, "reasons": ["overflow"]}')
        scorer = LLMScorer(self.baseline, provider, allow_network=True)
        self.assertEqual(scorer.score(self.lead).value, 100)

    def test_tolerates_prose_around_json(self):
        provider = FakeProvider(
            reply='Here you go: {"score": 50, "reasons": ["ok"]} thanks!'
        )
        scorer = LLMScorer(self.baseline, provider, allow_network=True)
        self.assertEqual(scorer.score(self.lead).value, 50)


if __name__ == "__main__":
    unittest.main()

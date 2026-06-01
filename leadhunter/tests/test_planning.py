"""Hermetic tests for the M3 planner — no network, no real LLM.

Covers the deterministic `RulePlanBuilder` floor and the optional
`LLMPlanBuilder`, whose every degradation path must fall back to the baseline.
The LLM is a local `FakeProvider` implementing the `LLMProvider` interface.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.llm.base import LLMProvider, LLMUnavailableError
from leadhunter.planning.base import DEFAULT_TARGET_COUNT, SearchPlan
from leadhunter.planning.rules import RulePlanBuilder
from leadhunter.planning.llm_planner import LLMPlanBuilder, build_plan


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


class RulePlanBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder = RulePlanBuilder()

    def test_parses_full_example(self):
        plan = self.builder.build(
            "Find 50 dentists in Austin TX with email and phone"
        )
        self.assertEqual(plan.vertical, "dentist")
        self.assertEqual(plan.location, "Austin TX")
        self.assertEqual(plan.required_fields, ("email", "phone"))
        self.assertEqual(plan.target_count, 50)
        self.assertEqual(plan.method, "rules")
        self.assertEqual(
            plan.raw_prompt, "Find 50 dentists in Austin TX with email and phone"
        )

    def test_default_count_when_absent(self):
        plan = self.builder.build("Find dentists in Austin")
        self.assertEqual(plan.target_count, DEFAULT_TARGET_COUNT)

    def test_no_required_fields_when_unmentioned(self):
        plan = self.builder.build("Find 10 plumbers in Dallas")
        self.assertEqual(plan.required_fields, ())

    def test_website_field_and_canonical_order(self):
        # Mentioned phone-then-email-then-website -> canonical email, phone, website.
        plan = self.builder.build(
            "Get 5 cafes in Reno with phone, website and email"
        )
        self.assertEqual(plan.required_fields, ("email", "phone", "website"))

    def test_singularization_variants(self):
        self.assertEqual(self.builder.build("20 agencies in NYC").vertical, "agency")
        self.assertEqual(
            self.builder.build("20 businesses in NYC").vertical, "business"
        )
        self.assertEqual(self.builder.build("20 dentists in NYC").vertical, "dentist")

    def test_multiword_vertical_singularizes_last_token(self):
        plan = self.builder.build("Find 12 dental clinics in Miami")
        self.assertEqual(plan.vertical, "dental clinic")

    def test_location_markers_near_and_around(self):
        self.assertEqual(self.builder.build("3 bakeries near Boston").location, "Boston")
        self.assertEqual(
            self.builder.build("3 bakeries around Boston").location, "Boston"
        )

    def test_no_location(self):
        plan = self.builder.build("Find 7 dentists")
        self.assertEqual(plan.location, "")
        self.assertEqual(plan.vertical, "dentist")

    def test_command_words_stripped_from_vertical(self):
        plan = self.builder.build("find me 9 law firms in Austin")
        self.assertEqual(plan.vertical, "law firm")

    def test_deterministic(self):
        prompt = "Find 50 dentists in Austin TX with email and phone"
        self.assertEqual(self.builder.build(prompt), self.builder.build(prompt))

    def test_count_floored_at_one(self):
        # SearchPlan.make floors the count; an explicit 0 cannot survive.
        plan = SearchPlan.make(
            vertical="x", location="y", required_fields=[],
            target_count=0, raw_prompt="", method="rules",
        )
        self.assertEqual(plan.target_count, 1)


class LLMPlanBuilderTests(unittest.TestCase):
    def setUp(self):
        self.baseline = RulePlanBuilder()
        self.prompt = "Find 50 dentists in Austin TX with email and phone"

    def test_uses_llm_when_allowed_and_available(self):
        provider = FakeProvider(
            reply='{"vertical": "orthodontist", "location": "Austin, Texas", '
            '"required_fields": ["email", "phone"], "target_count": 50}'
        )
        builder = LLMPlanBuilder(self.baseline, provider, allow_network=True)
        plan = builder.build(self.prompt)
        self.assertEqual(plan.vertical, "orthodontist")
        self.assertEqual(plan.location, "Austin, Texas")
        self.assertEqual(plan.method, "llm:fake")
        self.assertEqual(provider.calls, 1)

    def test_falls_back_when_network_not_allowed(self):
        provider = FakeProvider(reply='{"vertical": "x"}')
        builder = LLMPlanBuilder(self.baseline, provider, allow_network=False)
        self.assertEqual(builder.build(self.prompt), self.baseline.build(self.prompt))
        self.assertEqual(provider.calls, 0)  # provider never touched

    def test_falls_back_when_provider_none(self):
        builder = LLMPlanBuilder(self.baseline, None, allow_network=True)
        self.assertEqual(builder.build(self.prompt), self.baseline.build(self.prompt))

    def test_falls_back_when_unavailable(self):
        provider = FakeProvider(reply='{"vertical": "x"}', up=False)
        builder = LLMPlanBuilder(self.baseline, provider, allow_network=True)
        self.assertEqual(builder.build(self.prompt), self.baseline.build(self.prompt))
        self.assertEqual(provider.calls, 0)

    def test_falls_back_on_malformed_json(self):
        provider = FakeProvider(reply="sorry, I cannot help with that")
        builder = LLMPlanBuilder(self.baseline, provider, allow_network=True)
        self.assertEqual(builder.build(self.prompt), self.baseline.build(self.prompt))
        self.assertEqual(provider.calls, 1)  # tried, then fell back

    def test_falls_back_on_llm_error(self):
        provider = FakeProvider(raises=LLMUnavailableError("down"))
        builder = LLMPlanBuilder(self.baseline, provider, allow_network=True)
        self.assertEqual(builder.build(self.prompt), self.baseline.build(self.prompt))

    def test_partial_json_merges_over_baseline(self):
        # Model returns only a corrected count; other fields keep baseline values.
        provider = FakeProvider(reply='{"target_count": 75}')
        builder = LLMPlanBuilder(self.baseline, provider, allow_network=True)
        plan = builder.build(self.prompt)
        base = self.baseline.build(self.prompt)
        self.assertEqual(plan.target_count, 75)
        self.assertEqual(plan.vertical, base.vertical)
        self.assertEqual(plan.location, base.location)
        self.assertEqual(plan.required_fields, base.required_fields)

    def test_tolerates_prose_around_json(self):
        provider = FakeProvider(
            reply='Sure! {"vertical": "vet", "target_count": 8} hope that helps'
        )
        builder = LLMPlanBuilder(self.baseline, provider, allow_network=True)
        plan = builder.build(self.prompt)
        self.assertEqual(plan.vertical, "vet")
        self.assertEqual(plan.target_count, 8)


class BuildPlanDriverTests(unittest.TestCase):
    def test_rule_path_without_provider(self):
        plan = build_plan("Find 50 dentists in Austin TX with email and phone")
        self.assertEqual(plan.vertical, "dentist")
        self.assertEqual(plan.method, "rules")

    def test_llm_path_with_provider(self):
        provider = FakeProvider(
            reply='{"vertical": "dentist", "location": "Austin, TX", '
            '"required_fields": ["email", "phone"], "target_count": 50}'
        )
        plan = build_plan(
            "Find 50 dentists in Austin TX with email and phone",
            allow_network=True,
            provider=provider,
        )
        self.assertEqual(plan.method, "llm:fake")
        self.assertEqual(plan.location, "Austin, TX")


if __name__ == "__main__":
    unittest.main()

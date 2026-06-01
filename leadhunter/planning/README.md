# LeadHunter — planning (M3, Increment 1)

The front door of the locked objective: turn the single "Find Leads" box — one
natural-language prompt — into a structured, machine-readable **`SearchPlan`**
that downstream discovery/browsing/extraction can consume.

## Contract

```python
from leadhunter.planning import build_plan, RulePlanBuilder, LLMPlanBuilder

plan = build_plan("Find 50 dentists in Austin TX with email and phone")
# SearchPlan(vertical="dentist", location="Austin TX",
#            required_fields=("email", "phone"), target_count=50,
#            raw_prompt="...", method="rules")
```

Every builder implements the same `PlanBuilder` seam (`build(prompt) -> SearchPlan`),
mirroring the M2 scoring `Enricher`/`RuleScorer`/`LLMScorer` trio.

- **`RulePlanBuilder`** — deterministic, no-network baseline (the guaranteed
  floor). Pure regex/keyword parse: target count (first integer), required
  contact fields (`email`/`phone`/`website`), location (after `in`/`near`/…),
  and the business vertical (command words + count stripped, last token
  singularized). Always returns a valid plan, fully offline.
- **`LLMPlanBuilder`** — optional booster behind the same contract. Wraps a
  baseline + an optional `LLMProvider` (from `leadhunter.llm`). **Fail-closed**:
  if the network opt-in is off, no provider is configured, the provider is
  unavailable, or the reply is unparseable, it returns the baseline plan
  unchanged. When it does run, it *merges* over the baseline — any field the
  model omits keeps the baseline value, so the plan is always complete.
- **`build_plan(prompt, *, allow_network=False, provider=None)`** — convenience
  driver: baseline floor, plus LLM refinement when allowed and a reachable
  provider is supplied.

## Responsible use

Network access is opt-in, consistent with the rest of LeadHunter. No provider
method is called unless `allow_network=True`; the deterministic baseline needs
no network at all.

## Scope

This increment is purely the prompt → in-memory `SearchPlan` step. It performs
no discovery, browsing, or persistence — those are later M3+ increments.
Stdlib-only (`abc`, `dataclasses`, `re`, `json`). Hermetic tests mock the LLM
via an in-memory `FakeProvider`.

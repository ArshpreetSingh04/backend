"""LeadHunter planning (M3): the one-box prompt -> structured `SearchPlan` front door.

Public surface:
- `SearchPlan`, `PlanBuilder` — the planning contract.
- `RulePlanBuilder` — deterministic, no-network baseline (the guaranteed floor).
- `LLMPlanBuilder` — optional booster behind the same contract, fail-closed.
- `build_plan` — convenience driver (baseline floor + optional LLM refinement).
- `PlanError`, `DEFAULT_TARGET_COUNT`, `CANONICAL_FIELDS` — helpers/constants.
"""

from .base import (
    CANONICAL_FIELDS,
    DEFAULT_TARGET_COUNT,
    PlanBuilder,
    PlanError,
    SearchPlan,
    normalize_fields,
)
from .rules import RulePlanBuilder
from .llm_planner import LLMPlanBuilder, build_plan

__all__ = [
    "SearchPlan",
    "PlanBuilder",
    "PlanError",
    "RulePlanBuilder",
    "LLMPlanBuilder",
    "build_plan",
    "normalize_fields",
    "DEFAULT_TARGET_COUNT",
    "CANONICAL_FIELDS",
]

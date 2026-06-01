"""LeadHunter scoring (M2): deterministic baseline + optional LLM booster.

Public surface:
- `Score`, `Enricher` — the scoring contract.
- `RuleScorer` — deterministic, no-network baseline (the guaranteed floor).
- `LLMScorer` — optional booster behind the same contract, fail-closed.
- `ScoreStore`, `score_all` — dual-sink persistence (SQLite truth + CSV mirror).
"""

from .base import Enricher, Score, clamp_score, tier_for
from .rules import RuleScorer
from .llm_scorer import LLMScorer
from .score_store import ScoreStore, score_all

__all__ = [
    "Enricher",
    "Score",
    "clamp_score",
    "tier_for",
    "RuleScorer",
    "LLMScorer",
    "ScoreStore",
    "score_all",
]

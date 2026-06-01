# LeadHunter — Scoring (M2)

Turns a persisted `Lead` into a qualification **`Score`** (`value` 0–100,
`tier` cold/warm/hot, `reasons`, `method`). One contract, two implementations,
dual-sink persistence — all stdlib-only and hermetic.

## Contract (`base.py`)
```python
class Enricher(abc.ABC):
    def score(self, lead: Lead) -> Score: ...   # must never require the network
```
`Score.make(value, reasons, method)` clamps to 0–100 and derives the tier
(`<34` cold, `34–66` warm, `≥67` hot).

## Scorers
- **`RuleScorer` (`rules.py`)** — deterministic, no-I/O baseline and the
  guaranteed floor. Weighted identity signals: personal email +30 (role/shared
  mailbox like `info@`/`sales@` only +10), domain +20, company +15, contact
  name +15, phone +10, source url +10; clamped to 100.
- **`LLMScorer` (`llm_scorer.py`)** — optional booster behind the same
  contract. Wraps a baseline + an optional `LLMProvider` (from `llm.factory`).
  **Fail-closed:** if `allow_network=False`, no provider, provider unavailable,
  or the reply can't be parsed, it returns the baseline score unchanged — so it
  can only ever *improve* a valid score, never break the pipeline.

## Persistence (`score_store.py`)
`ScoreStore` mirrors the `LeadStore` pattern in its own `lead_scores` table:
SQLite is the source of truth, the CSV is regenerated from it after every write
so the two never diverge. `score_all(lead_store, score_store, scorer)` scores
every lead and upserts the results (idempotent; rescoring overwrites).

## Run the tests
```bash
python -m unittest discover -s leadhunter/tests
```
Hermetic: `LLMScorer` tests use an in-memory `FakeProvider` — no network, no
real LLM calls.

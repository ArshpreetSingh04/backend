# LeadHunter — Ingestion (M1 Increment 1)

Stdlib-only Python. No third-party deps, no network.

## What this provides
- **`model.py`** — `Lead` dataclass + layered, deterministic dedup key.
- **`normalize.py`** — `normalize_lead(raw)` to clean a source payload into a
  `Lead`, and `dedup(leads)` to collapse duplicates in memory.
- **`persistence.py`** — `LeadStore`: SQLite is the **source of truth**; the
  CSV is a **derived mirror** regenerated from SQLite after every write, so the
  two sinks can never diverge.

## Dedup key strategy (first non-empty layer wins)
1. `email:` lowercased email
2. `domain+company:` normalized domain + company (legal suffixes stripped)
3. `company+name:` normalized company + name
4. `hash:` sha1 of the sorted normalized field tuple (last-resort fallback)

The key is the SQLite PRIMARY KEY, so re-ingesting the same lead is idempotent
(`INSERT OR IGNORE`).

## Usage
```python
from leadhunter.ingestion import LeadStore, normalize_lead

store = LeadStore("data/leads.db", "data/leads.csv")
leads = [normalize_lead({"email": "jane@example.com", "company": "Example Inc"})]
store.add(leads)          # writes SQLite, then mirrors to CSV
store.all()               # read back from SQLite (truth)
```

## Run the tests
```
python -m unittest discover -s leadhunter/tests
```

## Deferred to later M1 increments (locked objective)
- Actual scrapers / human-like browsing.
- Pluggable LLM: local **Ollama** default + free hosted fallback.
- Responsible scraping behind an **opt-in** switch.
This increment only builds the persistence floor those pieces write into.

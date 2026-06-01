# discovery — candidate source discovery (M3 Increment 2)

Turn a structured `SearchPlan` (the parsed one-box prompt) into a **ranked list
of candidate sources** — descriptors of *where* to look for leads. Discovery
only *describes* candidates; it never fetches them. Acting on a candidate
(browsing/extraction) is a later milestone and stays behind the existing
network opt-in.

## Contract (`base.py`)
- `CandidateSource` — frozen record: `kind`, `name`, `query`, `risk`,
  `requires_network`, `rationale`, `score`, `rank`. `to_row`/`from_row`
  round-trip (ready for a future dual-sink store). `make()` validates the
  kind/risk vocabulary and derives `score`.
- `SourceDiscoverer` — the single seam: `discover(plan) -> [CandidateSource]`.
  `requires_network` flags the opt-in gate.
- `rank_candidates()` — deterministic total order: score desc, then name, then
  query; assigns a stable 0-based `rank`.

## Baseline (`rules.py`)
`RuleSourceDiscoverer` is the deterministic, **no-network** floor. It maps a
plan to one candidate per preference tier:
1. `official_api` — OpenStreetMap Overpass (structured open data, ODbL).
2. `structured_directory` — OpenStreetMap Nominatim (structured search API).
3. `web_search` — freeform open-web search (risky, unstructured).

## Driver (`pipeline.py`)
`discover_sources(plan, discoverers=None, *, allow_network=False)` runs the
discoverers (default: the offline baseline), merges + de-dupes by
`(kind, query)`, re-ranks, and returns `(DiscoverySummary, [CandidateSource])`.

## Responsible use
- **Prefer official/structured sources**: ranking hard-codes
  `official_api` > `structured_directory` > `web_search`, and higher `risk`
  is penalized, so the most-compliant sources surface first.
- **Isolate risky scraping**: freeform web candidates are tagged `risk="high"`
  and rank last; they are surfaced, never auto-run.
- **Fail-closed opt-in**: a discoverer with `requires_network = True` is refused
  with `DiscoveryNetworkNotAllowedError` unless `allow_network=True`. robots.txt
  / rate-limit / ToS handling lives in the ingestion network layer that
  *acts* on a candidate.

Stdlib-only, hermetic, purely additive.

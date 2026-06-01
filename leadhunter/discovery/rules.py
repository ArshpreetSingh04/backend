"""The deterministic, no-network discovery floor: `RuleSourceDiscoverer`.

Maps a `SearchPlan` to a small, ranked list of candidate sources with zero
network access — a pure function of the plan. Always prefers structured,
open-data / official sources and pushes freeform web search (risky, unstructured)
to the bottom, encoding the responsible-use posture directly in the ranking.

Stdlib-only (``re``).
"""

from __future__ import annotations

from typing import List

from ..planning.base import SearchPlan
from .base import (
    OFFICIAL_API,
    STRUCTURED_DIRECTORY,
    WEB_SEARCH,
    CandidateSource,
    SourceDiscoverer,
    rank_candidates,
)

# Vertical -> OpenStreetMap tag selector, for building an Overpass QL query.
# Unknown verticals fall back to a case-insensitive name match.
VERTICAL_OSM_TAGS = {
    "dentist": ("amenity", "dentist"),
    "doctor": ("amenity", "doctors"),
    "pharmacy": ("amenity", "pharmacy"),
    "restaurant": ("amenity", "restaurant"),
    "cafe": ("amenity", "cafe"),
    "bar": ("amenity", "bar"),
    "lawyer": ("office", "lawyer"),
    "accountant": ("office", "accountant"),
    "bakery": ("shop", "bakery"),
    "salon": ("shop", "hairdresser"),
    "gym": ("leisure", "fitness_centre"),
}


def _overpass_ql(vertical: str, location: str) -> str:
    """Build a deterministic Overpass QL string for ``vertical`` in ``location``.

    Uses a known OSM tag selector when the vertical is recognized, else a
    case-insensitive name match. When ``location`` is blank the area filter is
    omitted (an honest, still-deterministic query the caller can refine later).
    """
    v = (vertical or "").strip()
    tag = VERTICAL_OSM_TAGS.get(v.casefold())
    if tag:
        key, val = tag
        selector = f'["{key}"="{val}"]'
    else:
        safe = v.replace('"', "")
        selector = f'["name"~"{safe}",i]' if safe else ""

    loc = (location or "").strip().replace('"', "")
    if loc:
        prefix = f'area["name"="{loc}"]->.searchArea;'
        scope = "(area.searchArea)"
    else:
        prefix = ""
        scope = ""

    return (
        f"[out:json][timeout:30];{prefix}"
        f"(node{selector}{scope};way{selector}{scope};);"
        f"out tags;"
    )


def _web_query(plan: SearchPlan) -> str:
    """Compose a deterministic freeform search query from the plan."""
    parts = [plan.vertical, plan.location, *plan.required_fields]
    return " ".join(p.strip() for p in parts if p and p.strip())


class RuleSourceDiscoverer(SourceDiscoverer):
    """Deterministic baseline: `SearchPlan` -> ranked candidate sources.

    Emits one candidate per preference tier (official API, structured directory,
    web search), ranked so the safest/most-compliant source surfaces first.
    Performs no network access — ``requires_network`` stays ``False``.
    """

    name = "rules"
    requires_network = False

    def discover(self, plan: SearchPlan) -> List[CandidateSource]:
        vertical = (plan.vertical or "").strip()
        location = (plan.location or "").strip()
        where = f" in {location}" if location else ""

        candidates = [
            CandidateSource.make(
                kind=OFFICIAL_API,
                name="OpenStreetMap Overpass",
                query=_overpass_ql(vertical, location),
                risk="low",
                requires_network=True,
                rationale=(
                    "Structured open-data API (OpenStreetMap, ODbL); preferred "
                    "official source."
                ),
            ),
            CandidateSource.make(
                kind=STRUCTURED_DIRECTORY,
                name="OpenStreetMap Nominatim",
                query=f"{vertical}{where}".strip(),
                risk="low",
                requires_network=True,
                rationale=(
                    "Structured geocoding/search API; honor its usage policy and "
                    "rate limits."
                ),
            ),
            CandidateSource.make(
                kind=WEB_SEARCH,
                name="Open web search",
                query=_web_query(plan),
                risk="high",
                requires_network=True,
                rationale=(
                    "Freeform web search — unstructured and risky; opt-in network "
                    "only, robots.txt/rate-limits/ToS apply."
                ),
            ),
        ]
        return rank_candidates(candidates)

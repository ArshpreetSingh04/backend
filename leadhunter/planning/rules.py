"""Deterministic, no-network baseline planner.

`RulePlanBuilder` is the guaranteed floor for M3: a pure function of the prompt
text. It needs no LLM, performs no I/O, and always returns the same `SearchPlan`
for the same input, so the front door works fully offline. Stdlib-only (``re``).
"""

from __future__ import annotations

import re

from .base import (
    CANONICAL_FIELDS,
    DEFAULT_TARGET_COUNT,
    PlanBuilder,
    SearchPlan,
)

# Leading command phrases to strip from the vertical (longest first so that
# e.g. "find me" wins over "find").
_COMMAND_PHRASES = (
    "find me",
    "get me",
    "give me",
    "show me",
    "search for",
    "look for",
    "find",
    "get",
    "list",
    "generate",
    "fetch",
    "pull",
    "discover",
)

# Markers that introduce a location; the text before is the vertical-bearing head.
_LOCATION_MARKERS = (" located in ", " based in ", " in ", " near ", " around ")

# Marker that introduces the contact-field clause ("... with email and phone").
_WITH_MARKER = " with "

_INT_RE = re.compile(r"\d+")


def _detect_count(prompt: str) -> int:
    """First integer in the prompt, else the default target."""
    m = _INT_RE.search(prompt)
    return int(m.group()) if m else DEFAULT_TARGET_COUNT


def _detect_fields(prompt: str):
    """Contact fields named in the prompt, in canonical order."""
    low = prompt.casefold()
    found = []
    if "email" in low or "e-mail" in low:
        found.append("email")
    if "phone" in low or "telephone" in low or "mobile" in low:
        found.append("phone")
    if "website" in low or "web site" in low or "url" in low:
        found.append("website")
    return [f for f in CANONICAL_FIELDS if f in found]


def _strip_with_clause(text: str) -> str:
    """Drop a trailing ``with <fields>`` clause, leaving count+vertical+location."""
    idx = text.casefold().find(_WITH_MARKER)
    return text[:idx] if idx != -1 else text


def _split_location(head: str):
    """Split ``head`` at the earliest location marker -> (vertical_part, location)."""
    low = head.casefold()
    best_idx = -1
    best_len = 0
    for marker in _LOCATION_MARKERS:
        i = low.find(marker)
        if i != -1 and (best_idx == -1 or i < best_idx):
            best_idx = i
            best_len = len(marker)
    if best_idx == -1:
        return head, ""
    return head[:best_idx], head[best_idx + best_len :]


def _singularize(word: str) -> str:
    """Light singularizer for the vertical's last token (dentists -> dentist)."""
    low = word.casefold()
    if len(low) > 3 and low.endswith("ies"):
        return word[:-3] + "y"
    if len(low) > 3 and (
        low.endswith("ses")
        or low.endswith("shes")
        or low.endswith("ches")
        or low.endswith("xes")
    ):
        return word[:-2]
    if len(low) > 3 and low.endswith("s") and not low.endswith("ss"):
        return word[:-1]
    return word


def _clean_vertical(part: str) -> str:
    """Strip command phrases + the count from ``part`` and singularize the type."""
    s = part.strip()
    # Peel any leading command phrases (possibly stacked, e.g. "find me").
    changed = True
    while changed:
        changed = False
        low = s.casefold()
        for cmd in _COMMAND_PHRASES:
            if low == cmd or low.startswith(cmd + " "):
                s = s[len(cmd):].strip()
                changed = True
                break
    # Drop standalone integer tokens (the count).
    tokens = [t for t in s.split() if not t.isdigit()]
    s = " ".join(tokens).strip(" ,.")
    if not s:
        return ""
    parts = s.split()
    parts[-1] = _singularize(parts[-1])
    return " ".join(parts)


class RulePlanBuilder(PlanBuilder):
    """Transparent regex/keyword parse of a one-box prompt into a `SearchPlan`."""

    name = "rules"

    def build(self, prompt: str) -> SearchPlan:
        text = (prompt or "").strip()
        head = _strip_with_clause(text)
        vertical_part, location = _split_location(head)
        return SearchPlan.make(
            vertical=_clean_vertical(vertical_part),
            location=" ".join(location.split()).strip(" ,."),
            required_fields=_detect_fields(text),
            target_count=_detect_count(text),
            raw_prompt=prompt or "",
            method=self.name,
        )

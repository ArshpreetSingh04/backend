"""Opt-in network enrichment: fill email/phone from the lead's OWN website.

`WebContactEnricher` is M2's first **network** identity enricher. It fills the
`email` and `phone` fields that cannot be derived deterministically (so they are
out of `DerivationEnricher`'s scope) by fetching the organisation's *own*
published website — the contact details a business publishes for exactly this
purpose — and parsing ``mailto:``/``tel:`` links (with a plain-text email
fallback). Reading the owner's own published contact page is the responsible
choice: it is not third-party scraping, an aggregator, or a paid data broker.

Responsible-use contract (mirrors the ingestion `OverpassSource`):
- ``requires_network = True`` so the driver refuses this enricher unless the
  caller explicitly opts in with ``allow_network=True`` (fail closed). No
  network I/O happens at construction — only inside ``enrich()``, and only when
  there is something to fill and a fetchable target.
- ``robots.txt`` is honored before the page is fetched.
- Requests carry a descriptive ``User-Agent``, a bounded ``timeout``, a bounded
  ``max_bytes`` read, and a polite inter-request ``delay``.

Like every `IdentityEnricher`, it only ever **fills empty** fields (never
overwrites) and preserves the lead's ``dedup_key`` so persistence identity stays
stable even when the top-priority ``email`` field is populated.

Stdlib-only: ``urllib`` (request / parse / robotparser), ``re``, ``time``,
``dataclasses``, ``html``.
"""

from __future__ import annotations

import html
import re
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import replace
from typing import Callable, Optional

from ..ingestion.model import Lead
from .base import EnrichResult, IdentityEnricher

DEFAULT_USER_AGENT = "LeadHunter/0.1 (+https://github.com/ArshpreetSingh04/backend)"

# A pragmatic email pattern for the plain-text fallback (mailto: is preferred).
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# mailto:/tel: hrefs, capturing the address up to a quote, '#', '?' or space.
_MAILTO_RE = re.compile(r"""mailto:([^"'>?\s#]+)""", re.IGNORECASE)
_TEL_RE = re.compile(r"""tel:([^"'>?\s#]+)""", re.IGNORECASE)


class RobotsDisallowedError(RuntimeError):
    """Raised when robots.txt forbids fetching the lead's website."""


class WebContactEnricher(IdentityEnricher):
    """Fill empty ``email``/``phone`` from the lead's own published website.

    ``enrich()`` short-circuits (no network) when both fields are already set or
    when the lead has no fetchable website. Otherwise it performs (optionally) a
    robots.txt check, a polite delay, one HTTP GET, then fills only the empty
    contact fields from what the page publishes.
    """

    name = "web_contact"
    requires_network = True

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        delay: float = 1.0,
        user_agent: str = DEFAULT_USER_AGENT,
        check_robots: bool = True,
        max_bytes: int = 1_000_000,
        sleep: Optional[Callable[[float], None]] = None,
    ) -> None:
        # No network here — construction is side-effect free so the driver's
        # opt-in guard can refuse this enricher before any I/O is attempted.
        self.timeout = timeout
        self.delay = delay
        self.user_agent = user_agent
        self.check_robots = check_robots
        self.max_bytes = max_bytes
        self._sleep = sleep or time.sleep

    def enrich(self, lead: Lead) -> EnrichResult:
        # Nothing to do if both contact fields are already populated.
        need_email = not (lead.email or "").strip()
        need_phone = not (lead.phone or "").strip()
        if not (need_email or need_phone):
            return EnrichResult(lead=lead, filled=(), method=self.name)

        url = self._base_url(lead)
        if not url:
            return EnrichResult(lead=lead, filled=(), method=self.name)

        if self.check_robots:
            self._check_robots(url)
        if self.delay:
            self._sleep(self.delay)
        body = self._http_get(url)

        updates = {}
        if need_email:
            email = self._extract_email(body)
            if email:
                updates["email"] = email
        if need_phone:
            phone = self._extract_phone(body)
            if phone:
                updates["phone"] = phone

        if not updates:
            return EnrichResult(lead=lead, filled=(), method=self.name)

        # Preserve dedup_key explicitly: filling email must not re-key the lead.
        new_lead = replace(lead, dedup_key=lead.dedup_key, **updates)
        return EnrichResult(
            lead=new_lead,
            filled=tuple(sorted(updates)),
            method=self.name,
        )

    # -- target selection -------------------------------------------------

    @staticmethod
    def _base_url(lead: Lead) -> str:
        """Build the lead's own homepage URL from source_url or domain.

        Prefers ``source_url`` when it carries a host; otherwise falls back to
        ``https://<domain>``. Returns "" when neither yields a host.
        """
        source_url = (lead.source_url or "").strip()
        if source_url:
            candidate = source_url
            if "://" not in candidate:
                candidate = "http://" + candidate
            parts = urllib.parse.urlsplit(candidate)
            if parts.hostname:
                return candidate

        domain = (lead.domain or "").strip()
        if domain:
            return "https://" + domain
        return ""

    # -- responsible-use helpers -----------------------------------------

    def _check_robots(self, url: str) -> None:
        """Honor robots.txt for ``url``'s host; raise if the path is disallowed."""
        parts = urllib.parse.urlsplit(url)
        robots_url = urllib.parse.urlunsplit(
            (parts.scheme, parts.netloc, "/robots.txt", "", "")
        )
        try:
            text = self._http_get(robots_url)
        except Exception:
            # No reachable robots.txt -> nothing disallowed; proceed politely.
            return
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(text.splitlines())
        if not parser.can_fetch(self.user_agent, url):
            raise RobotsDisallowedError(f"robots.txt disallows fetching {url!r}")

    # -- single network seam (overridden in tests for hermeticity) --------

    def _http_get(self, url: str) -> str:
        """Perform one HTTP GET and return the decoded body text.

        This is the only method that touches the network; tests override it to
        return canned fixtures. The read is bounded by ``max_bytes``.
        """
        request = urllib.request.Request(
            url, headers={"User-Agent": self.user_agent}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            data = response.read(self.max_bytes)
            return data.decode(charset, errors="replace")

    # -- parsing ----------------------------------------------------------

    @classmethod
    def _extract_email(cls, body: str) -> str:
        """Return the first published email (mailto: preferred), or ""."""
        text = html.unescape(body or "")
        match = _MAILTO_RE.search(text)
        if match:
            candidate = match.group(1).split(",")[0].strip()
            if _EMAIL_RE.fullmatch(candidate):
                return candidate.casefold()
        match = _EMAIL_RE.search(text)
        if match:
            return match.group(0).casefold()
        return ""

    @classmethod
    def _extract_phone(cls, body: str) -> str:
        """Return the first published phone from a tel: link, or ""."""
        text = html.unescape(body or "")
        match = _TEL_RE.search(text)
        if match:
            return match.group(1).strip()
        return ""

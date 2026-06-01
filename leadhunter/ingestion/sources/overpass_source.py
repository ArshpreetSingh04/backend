"""First network-backed ingestion source: the OpenStreetMap Overpass API.

Overpass is a public, open-data read API over OpenStreetMap (data licensed
ODbL). Business POIs carry contact tags (``name``, ``website``, ``phone``,
``email``) that map cleanly onto a `Lead`. This is a structured open-data API,
not HTML scraping — the responsible choice for the first network source.

Responsible-use contract:
- ``requires_network = True`` so the pipeline refuses this source unless the
  caller explicitly opts in with ``allow_network=True`` (fail closed). No
  network I/O happens at construction; it only happens inside ``records()``.
- ``robots.txt`` is honored before querying the endpoint.
- Requests carry a descriptive ``User-Agent`` (required by OSM policy), a
  bounded timeout, and a polite inter-request delay.

Stdlib-only: ``urllib`` (request / parse / robotparser), ``json``, ``time``.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from typing import Any, Callable, Dict, Iterator, Mapping, Optional

from .base import Source

DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"
DEFAULT_USER_AGENT = "LeadHunter/0.1 (+https://github.com/ArshpreetSingh04/backend)"

# OSM tag keys checked (in order) for each logical contact field.
_WEBSITE_KEYS = ("website", "contact:website", "url")
_PHONE_KEYS = ("phone", "contact:phone", "telephone")
_EMAIL_KEYS = ("email", "contact:email")


class RobotsDisallowedError(RuntimeError):
    """Raised when robots.txt forbids fetching the Overpass endpoint."""


class OverpassSource(Source):
    """Yield raw lead payloads from an OpenStreetMap Overpass API query.

    The query is an Overpass QL string. ``records()`` performs (optional) a
    robots.txt check, a polite delay, one HTTP POST, then yields one raw
    payload dict per element that has a usable identity. Elements lacking any
    identity (no name and no contact details) are skipped at the source;
    normalization and dedup still run downstream on what remains.
    """

    requires_network = True

    def __init__(
        self,
        query: str,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 30.0,
        delay: float = 1.0,
        user_agent: str = DEFAULT_USER_AGENT,
        check_robots: bool = True,
        name: str = "overpass",
        sleep: Optional[Callable[[float], None]] = None,
    ) -> None:
        # No network here — construction is side-effect free so the pipeline's
        # opt-in guard can refuse this source before any I/O is attempted.
        self.query = query
        self.endpoint = endpoint
        self.timeout = timeout
        self.delay = delay
        self.user_agent = user_agent
        self.check_robots = check_robots
        self.name = name
        self._sleep = sleep or time.sleep

    def records(self) -> Iterator[Mapping[str, Any]]:
        if self.check_robots:
            self._check_robots()
        if self.delay:
            self._sleep(self.delay)
        body = self._http_get(
            self.endpoint, data=self.query.encode("utf-8")
        )
        payload = json.loads(body)
        for element in payload.get("elements", []):
            mapped = self._element_to_payload(element)
            if mapped is not None:
                yield mapped

    # -- responsible-use helpers ------------------------------------------

    def _check_robots(self) -> None:
        """Honor robots.txt for the endpoint; raise if the path is disallowed."""
        parts = urllib.parse.urlsplit(self.endpoint)
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
        if not parser.can_fetch(self.user_agent, self.endpoint):
            raise RobotsDisallowedError(
                f"robots.txt disallows fetching {self.endpoint!r}"
            )

    # -- single network seam (overridden in tests for hermeticity) --------

    def _http_get(self, url: str, *, data: Optional[bytes] = None) -> str:
        """Perform one HTTP request and return the decoded body text.

        GET when ``data`` is None, POST otherwise. This is the only method that
        touches the network; tests override it to return canned fixtures.
        """
        request = urllib.request.Request(
            url, data=data, headers={"User-Agent": self.user_agent}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)

    # -- mapping ----------------------------------------------------------

    @staticmethod
    def _first_tag(tags: Mapping[str, Any], keys) -> str:
        for key in keys:
            value = tags.get(key)
            if value:
                return str(value).strip()
        return ""

    @staticmethod
    def _website_to_domain(website: str) -> str:
        """Extract a bare host from a website URL (drop scheme/path/www.)."""
        if not website:
            return ""
        candidate = website.strip()
        if "//" not in candidate:
            candidate = "//" + candidate  # let urlsplit treat it as netloc
        host = urllib.parse.urlsplit(candidate).netloc
        host = host.split("@")[-1].split(":")[0].casefold()
        if host.startswith("www."):
            host = host[4:]
        return host

    def _element_to_payload(
        self, element: Mapping[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Map one OSM element to a raw lead payload, or None to skip it."""
        tags = element.get("tags") or {}
        company = str(tags.get("name", "")).strip()
        website = self._first_tag(tags, _WEBSITE_KEYS)
        domain = self._website_to_domain(website)
        phone = self._first_tag(tags, _PHONE_KEYS)
        email = self._first_tag(tags, _EMAIL_KEYS)

        # Skip obvious junk: no name and no contact handle of any kind.
        if not (company or domain or phone or email):
            return None

        osm_type = element.get("type", "")
        osm_id = element.get("id", "")
        source_url = (
            f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
            if osm_type and osm_id != ""
            else ""
        )
        return {
            "name": "",
            "company": company,
            "email": email,
            "domain": domain,
            "phone": phone,
            "source": self.name,
            "source_url": source_url,
            "raw": dict(element),
        }

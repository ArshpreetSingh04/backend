"""Source abstraction and the responsible-use network guard.

A `Source` produces raw payload dicts (pre-normalization). Each source declares
whether it needs network access. The pipeline enforces an opt-in switch: a
network-requiring source is refused unless the caller explicitly opts in, so
later scrapers fail loudly instead of silently reaching the network.
"""

from __future__ import annotations

import abc
from typing import Any, Iterator, Mapping


class NetworkNotAllowedError(RuntimeError):
    """Raised when a network-requiring source runs without an explicit opt-in.

    Responsible-use contract: scraping/network access is opt-in only. Sources
    that set ``requires_network = True`` may only run when the pipeline is
    invoked with ``allow_network=True``.
    """


class Source(abc.ABC):
    """Base class for ingestion sources.

    Subclasses yield raw payload dicts from ``records()``. The
    ``requires_network`` flag gates the responsible-use opt-in switch enforced
    by the pipeline; the first file-based source keeps it ``False``.
    """

    #: Human-readable source name, also stamped onto leads via normalization.
    name: str = "source"

    #: Whether running this source performs network access (opt-in gated).
    requires_network: bool = False

    @abc.abstractmethod
    def records(self) -> Iterator[Mapping[str, Any]]:
        """Yield raw payload dicts (no normalization, no dedup, no I/O side effects)."""
        raise NotImplementedError

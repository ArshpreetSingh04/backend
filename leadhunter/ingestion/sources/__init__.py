"""Ingestion sources for LeadHunter.

A *source* yields raw payload dicts that the pipeline normalizes, dedups, and
persists. The first concrete source (`FileSource`) is offline/stdlib-only.

Network-backed sources (scrapers) arrive in a later increment and must declare
``requires_network = True``; the pipeline refuses them unless network use is
explicitly opted in. See ``base.py`` and ``pipeline.py``.
"""

from .base import Source, NetworkNotAllowedError
from .file_source import FileSource

__all__ = ["Source", "NetworkNotAllowedError", "FileSource"]

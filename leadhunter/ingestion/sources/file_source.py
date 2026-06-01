"""Offline file-based ingestion source (CSV / JSON / JSONL).

The first concrete `Source`. Reads local files only — no network — using the
stdlib (`csv`, `json`). Format is detected by file extension:

- ``.csv``   -> rows via ``csv.DictReader`` (header row -> keys)
- ``.json``  -> a top-level JSON array of objects (or a single object)
- ``.jsonl`` / ``.ndjson`` -> one JSON object per non-blank line

Blank lines and an empty file yield no records. Each yielded dict is a raw
payload; normalization/dedup happen downstream in the pipeline.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterator, Mapping

from .base import Source


class UnsupportedFileFormatError(ValueError):
    """Raised when a file's extension is not a supported ingestion format."""


_JSONL_SUFFIXES = {".jsonl", ".ndjson"}


class FileSource(Source):
    """Yield raw lead payloads from a local CSV / JSON / JSONL file."""

    requires_network = False

    def __init__(self, path: str, *, name: str = "file") -> None:
        self.path = Path(path)
        self.name = name

    def _suffix(self) -> str:
        return self.path.suffix.casefold()

    def records(self) -> Iterator[Mapping[str, Any]]:
        suffix = self._suffix()
        if suffix == ".csv":
            yield from self._read_csv()
        elif suffix in _JSONL_SUFFIXES:
            yield from self._read_jsonl()
        elif suffix == ".json":
            yield from self._read_json()
        else:
            raise UnsupportedFileFormatError(
                f"Unsupported file format: {self.path.suffix!r} ({self.path})"
            )

    def _read_csv(self) -> Iterator[Mapping[str, Any]]:
        with open(self.path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                # Skip fully blank rows (DictReader yields all-empty dicts).
                if any((v or "").strip() for v in row.values()):
                    yield dict(row)

    def _read_jsonl(self) -> Iterator[Mapping[str, Any]]:
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def _read_json(self) -> Iterator[Mapping[str, Any]]:
        with open(self.path, "r", encoding="utf-8") as fh:
            text = fh.read().strip()
        if not text:
            return
        data = json.loads(text)
        if isinstance(data, dict):
            yield data
        elif isinstance(data, list):
            for item in data:
                yield item
        else:
            raise UnsupportedFileFormatError(
                f"JSON root must be an object or array of objects, got {type(data).__name__}"
            )

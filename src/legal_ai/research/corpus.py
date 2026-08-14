"""Deterministic selection over recorded WA fixtures.

This module performs local, read-only filesystem reads of durable
version-controlled fixtures beneath an **injected** root. It performs no
network access, no live retrieval, and no persistence, and it holds no default
path: the caller (a test harness) supplies the corpus root.

Manifest content is untrusted recorded data. It is read as data only: values
are never coerced, never executed, and never used to widen the read boundary.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import AmbiguousSelection, RecordedCorpusError
from .models import MAX_SOURCE_CONTENT_BYTES, RecordedProvision, RecordedWaSource, ResearchQuery

_MANIFEST_SUFFIX = "*.manifest.json"
_MAX_MANIFEST_BYTES = 1_048_576


def normalize_for_match(value: str) -> str:
    """Return a deterministic comparison key: collapsed whitespace, casefolded."""

    return " ".join(value.split()).casefold()


def _opt_str(mapping: Mapping[str, object], key: str) -> str | None:
    value = mapping.get(key)
    return value if isinstance(value, str) else None


def _opt_bool(mapping: Mapping[str, object], key: str) -> bool | None:
    value = mapping.get(key)
    return value if isinstance(value, bool) else None


def _opt_mapping(mapping: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = mapping.get(key)
    return value if isinstance(value, Mapping) else {}


def _provisions(mapping: Mapping[str, object]) -> tuple[RecordedProvision, ...]:
    recorded = mapping.get("provisions")
    if not isinstance(recorded, Sequence) or isinstance(recorded, str | bytes):
        return ()
    provisions: list[RecordedProvision] = []
    for entry in recorded:
        if not isinstance(entry, Mapping):
            continue
        identifier = _opt_str(entry, "identifier")
        pinpoint = _opt_str(entry, "pinpoint")
        if identifier is None or pinpoint is None or not identifier.strip() or not pinpoint.strip():
            continue
        provisions.append(
            RecordedProvision(
                identifier=identifier,
                pinpoint=pinpoint,
                heading=_opt_str(entry, "heading"),
            )
        )
    return tuple(provisions)


def _safe_content_path(manifest_path: Path, filename: str, root: Path) -> Path:
    """Resolve a manifest-declared content file without leaving the fixture root."""

    if not filename.strip() or filename in {".", ".."}:
        raise RecordedCorpusError("recorded content filename is blank")
    if "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise RecordedCorpusError("recorded content filename must be a plain basename")
    candidate = (manifest_path.parent / filename).resolve()
    if not candidate.is_relative_to(root) or candidate.is_symlink() or not candidate.is_file():
        raise RecordedCorpusError("recorded content file is not a regular file inside the root")
    return candidate


@dataclass(frozen=True, slots=True)
class _ManifestEntry:
    manifest_path: Path
    content_path: Path
    fields: Mapping[str, object]


class RecordedSourceCorpus(Protocol):
    """Deterministic recorded-source selection contract."""

    def select(self, query: ResearchQuery) -> RecordedWaSource | None:
        """Return the single recorded source for the query, or None."""


class RecordedWaCorpus:
    """Recorded WA fixtures loaded from an injected, read-only root."""

    def __init__(self, root: Path) -> None:
        try:
            self._root = Path(root).resolve(strict=True)
        except OSError as exc:
            raise RecordedCorpusError("recorded fixture root could not be resolved") from exc
        if not self._root.is_dir():
            raise RecordedCorpusError("recorded fixture root is not a directory")
        self._entries = tuple(self._load_entries())

    def _load_entries(self) -> list[_ManifestEntry]:
        entries: list[_ManifestEntry] = []
        for manifest_path in sorted(self._root.rglob(_MANIFEST_SUFFIX), key=lambda p: p.as_posix()):
            resolved = manifest_path.resolve()
            if not resolved.is_relative_to(self._root) or not resolved.is_file():
                raise RecordedCorpusError("recorded manifest is outside the fixture root")
            if resolved.stat().st_size > _MAX_MANIFEST_BYTES:
                raise RecordedCorpusError("recorded manifest exceeds the maximum manifest size")
            try:
                parsed = json.loads(resolved.read_bytes())
            except (OSError, ValueError) as exc:
                raise RecordedCorpusError("recorded manifest could not be parsed") from exc
            if not isinstance(parsed, Mapping):
                raise RecordedCorpusError("recorded manifest is not a JSON object")
            filename = _opt_str(parsed, "file")
            if filename is None:
                raise RecordedCorpusError("recorded manifest declares no content file")
            entries.append(
                _ManifestEntry(
                    manifest_path=resolved,
                    content_path=_safe_content_path(resolved, filename, self._root),
                    fields=parsed,
                )
            )
        return entries

    def select(self, query: ResearchQuery) -> RecordedWaSource | None:
        """Return the single recorded source whose Act identity matches the query.

        Selection is deterministic and total: an empty match refuses upstream as
        a missing retrieval, and a non-unique match raises rather than guessing.
        """

        wanted = normalize_for_match(query.act_title)
        matches = [
            entry
            for entry in self._entries
            if normalize_for_match(_opt_str(_opt_mapping(entry.fields, "act"), "title") or "")
            == wanted
        ]
        if not matches:
            return None
        if len(matches) > 1:
            raise AmbiguousSelection("recorded corpus holds more than one source for the Act")
        return self._read(matches[0])

    @staticmethod
    def _read(entry: _ManifestEntry) -> RecordedWaSource:
        fields = entry.fields
        act = _opt_mapping(fields, "act")
        version = _opt_mapping(fields, "version")
        status = _opt_mapping(fields, "status")
        try:
            if entry.content_path.stat().st_size > MAX_SOURCE_CONTENT_BYTES:
                raise RecordedCorpusError("recorded content exceeds the maximum content size")
            content = entry.content_path.read_bytes()
        except OSError as exc:
            raise RecordedCorpusError("recorded content could not be read") from exc
        return RecordedWaSource(
            source_id=_opt_str(fields, "source_id"),
            source_system=_opt_str(fields, "source_system"),
            jurisdiction=_opt_str(fields, "jurisdiction"),
            act_title=_opt_str(act, "title"),
            act_jurisdiction=_opt_str(act, "jurisdiction"),
            act_number=_opt_str(act, "act_number"),
            official_source_url=_opt_str(fields, "official_source_url"),
            provisions=_provisions(fields),
            source_version=_opt_str(version, "suffix"),
            compilation_date=_opt_str(version, "currency_start"),
            status_currency=_opt_str(status, "currency"),
            status_in_force=_opt_bool(status, "in_force"),
            status_date=_opt_str(status, "status_date"),
            retrieved_at=_opt_str(fields, "retrieved_at_utc"),
            sha256=_opt_str(fields, "sha256"),
            source_content=content,
        )

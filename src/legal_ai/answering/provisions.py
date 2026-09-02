"""Digest-chained derived provision text.

A validated `WaEvidencePacket` carries the exact bytes of a whole official
instrument, which for a consolidated Act is a large PDF. A model cannot be
handed that, so `scripts/derive_wa_provisions.py` derives per-provision text
offline and records the digest of the parent it came from.

This module is the read side, and it trusts nothing:

- the recorded parent digest must equal the digest of the packet in hand;
- the recorded provision identity must equal the packet's;
- the text file's digest must equal the digest recorded for it.

Any mismatch resolves to `None`, and the pipeline then answers from identity
fields alone rather than from unverified text. Derived text is data, never
instruction.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..research.models import WaEvidencePacket

_MANIFEST_SUFFIX = "*.provision.json"
_MAX_MANIFEST_BYTES = 262_144
MAX_PROVISION_TEXT_BYTES = 1_048_576


@dataclass(frozen=True, slots=True)
class DerivedProvision:
    """Provision text whose provenance chain back to the packet is verified."""

    provision_identifier: str
    pinpoint: str
    heading: str | None
    text: str
    sha256: str
    parent_sha256: str


class DerivedProvisionStore(Protocol):
    """Resolve verified derived text for one evidence packet."""

    def resolve(self, packet: WaEvidencePacket) -> DerivedProvision | None:
        """Return verified derived text for the packet, or None."""


class NullDerivedProvisionStore:
    """A store that never resolves text. The pipeline default."""

    def resolve(self, packet: WaEvidencePacket) -> DerivedProvision | None:
        """Return None for every packet."""

        del packet
        return None


def _opt_str(mapping: Mapping[str, object], key: str) -> str | None:
    value = mapping.get(key)
    return value if isinstance(value, str) else None


class FileDerivedProvisionStore:
    """Derived provision text loaded from an injected, read-only root."""

    def __init__(self, root: Path) -> None:
        self._records: dict[tuple[str, str], DerivedProvision] = {}
        try:
            resolved_root = Path(root).resolve(strict=True)
        except OSError:
            return
        if not resolved_root.is_dir():
            return
        for manifest in sorted(resolved_root.rglob(_MANIFEST_SUFFIX), key=lambda p: p.as_posix()):
            record = self._load(manifest, resolved_root)
            if record is not None:
                self._records[(record.parent_sha256, record.provision_identifier)] = record

    @staticmethod
    def _load(manifest_path: Path, root: Path) -> DerivedProvision | None:
        """Load one manifest, returning None unless every check passes."""

        try:
            resolved = manifest_path.resolve()
            if not resolved.is_relative_to(root) or not resolved.is_file():
                return None
            if resolved.stat().st_size > _MAX_MANIFEST_BYTES:
                return None
            parsed = json.loads(resolved.read_bytes())
        except (OSError, ValueError):
            return None
        if not isinstance(parsed, Mapping):
            return None

        filename = _opt_str(parsed, "file")
        parent_sha256 = _opt_str(parsed, "parent_sha256")
        identifier = _opt_str(parsed, "provision_identifier")
        pinpoint = _opt_str(parsed, "pinpoint")
        recorded_digest = _opt_str(parsed, "sha256")
        if None in (filename, parent_sha256, identifier, pinpoint, recorded_digest):
            return None
        assert filename is not None  # narrowed above; keeps the type checker exact
        if "/" in filename or "\\" in filename or Path(filename).name != filename:
            return None

        try:
            text_path = (resolved.parent / filename).resolve()
            if not text_path.is_relative_to(root) or text_path.is_symlink():
                return None
            if not text_path.is_file() or text_path.stat().st_size > MAX_PROVISION_TEXT_BYTES:
                return None
            content = text_path.read_bytes()
        except OSError:
            return None

        if hashlib.sha256(content).hexdigest() != recorded_digest:
            return None
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if not text.strip():
            return None

        assert parent_sha256 is not None and identifier is not None
        assert pinpoint is not None and recorded_digest is not None
        return DerivedProvision(
            provision_identifier=identifier,
            pinpoint=pinpoint,
            heading=_opt_str(parsed, "heading"),
            text=text,
            sha256=recorded_digest,
            parent_sha256=parent_sha256,
        )

    def resolve(self, packet: WaEvidencePacket) -> DerivedProvision | None:
        """Return derived text whose chain matches this exact packet."""

        record = self._records.get((packet.sha256, packet.provision_identifier))
        if record is None:
            return None
        if record.pinpoint != packet.pinpoint:
            return None
        return record

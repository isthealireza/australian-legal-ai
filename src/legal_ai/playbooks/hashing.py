"""Project canonical JSON hashing for playbook definition payloads.

Canonical form: sorted object keys, schema-defined array order preserved,
compact UTF-8 JSON (separators(',', ':'), ensure_ascii=False).
Does not claim RFC 8785 / JCS compliance.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    raise TypeError(f"unsupported definition value type: {type(value)!r}")


def canonical_definition_bytes(payload: dict[str, Any]) -> bytes:
    """Return canonical UTF-8 bytes for a definition payload dict."""

    canonical = _canonical_value(payload)
    if not isinstance(canonical, dict):
        raise TypeError("definition payload must be an object")
    return json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def content_sha256(payload: dict[str, Any]) -> str:
    """SHA-256 hex digest of the canonical definition payload only."""

    digest = hashlib.sha256(canonical_definition_bytes(payload)).hexdigest()
    return digest

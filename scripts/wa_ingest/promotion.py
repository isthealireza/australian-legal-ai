"""The promotion gate: staged to active corpus root.

Promotion is the moment legal content enters the corpus, so this module is
written to refuse. Every precondition returns a typed reason and the active
root is touched only after all of them pass.

Two refusals exist that no amount of correct engineering can satisfy, and that
is deliberate:

- `OWNER_APPROVAL_MISSING` / `OWNER_APPROVAL_MISMATCH` — gate G1. An owner must
  have accepted the exact URL, version, currency date and retrieval timestamp.
- `SECTION_VERIFIED_WITHOUT_RECORD` — gate G2. A section may carry
  `verified: true` only when a human verification record names who compared it
  against the official document.

Both gates are human acts. This module can only check that they happened.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from scripts.wa_ingest.extraction import section_text_digest
from scripts.wa_ingest.staging import StagingLayout, compute_digest, slug_for_title

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PromotionRefusal(StrEnum):
    """Why a staged source may not enter the active corpus."""

    STAGING_INCOMPLETE = "STAGING_INCOMPLETE"
    MANIFEST_UNREADABLE = "MANIFEST_UNREADABLE"
    MANIFEST_DIGEST_MISMATCH = "MANIFEST_DIGEST_MISMATCH"
    SECTIONS_UNREADABLE = "SECTIONS_UNREADABLE"
    SECTIONS_SOURCE_MISMATCH = "SECTIONS_SOURCE_MISMATCH"
    SECTION_TEXT_HASH_MISMATCH = "SECTION_TEXT_HASH_MISMATCH"
    SECTION_IDENTIFIER_AMBIGUOUS = "SECTION_IDENTIFIER_AMBIGUOUS"
    SECTION_NOT_IN_MANIFEST = "SECTION_NOT_IN_MANIFEST"
    SECTION_VERIFIED_WITHOUT_RECORD = "SECTION_VERIFIED_WITHOUT_RECORD"
    PROVISION_IDENTIFIER_AMBIGUOUS = "PROVISION_IDENTIFIER_AMBIGUOUS"
    PROVISIONS_EMPTY = "PROVISIONS_EMPTY"
    EXTRACTION_TOOL_UNRECORDED = "EXTRACTION_TOOL_UNRECORDED"
    OWNER_APPROVAL_MISSING = "OWNER_APPROVAL_MISSING"
    OWNER_APPROVAL_MISMATCH = "OWNER_APPROVAL_MISMATCH"
    ACT_TITLE_ALREADY_PRESENT = "ACT_TITLE_ALREADY_PRESENT"
    TARGET_ALREADY_EXISTS = "TARGET_ALREADY_EXISTS"


@dataclass(frozen=True, slots=True)
class PromotionPlan:
    """A staged source that passed every precondition."""

    layout: StagingLayout
    target_directory: Path
    manifest: dict[str, Any]
    sections: dict[str, Any]


def _normalise(value: str) -> str:
    return " ".join(value.split()).casefold()


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _citation_keys(provision: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for field in ("identifier", "pinpoint"):
        value = provision.get(field)
        if isinstance(value, str) and value.strip():
            keys.add(_normalise(value))
    return keys


def check_promotion(
    *,
    layout: StagingLayout,
    active_root: Path,
) -> PromotionPlan | PromotionRefusal:
    """Return a plan, or the first reason this source may not be promoted."""

    if not (
        layout.pdf_path.is_file()
        and layout.manifest_path.is_file()
        and layout.sections_path.is_file()
    ):
        return PromotionRefusal.STAGING_INCOMPLETE

    manifest = _load_json(layout.manifest_path)
    if manifest is None:
        return PromotionRefusal.MANIFEST_UNREADABLE

    recorded_digest = manifest.get("sha256")
    if not isinstance(recorded_digest, str) or not _SHA256.match(recorded_digest):
        return PromotionRefusal.MANIFEST_UNREADABLE
    if compute_digest(layout.pdf_path) != recorded_digest:
        return PromotionRefusal.MANIFEST_DIGEST_MISMATCH

    provisions = manifest.get("provisions")
    if not isinstance(provisions, list) or not provisions:
        return PromotionRefusal.PROVISIONS_EMPTY

    seen_citations: set[str] = set()
    declared: set[str] = set()
    for provision in provisions:
        if not isinstance(provision, dict):
            return PromotionRefusal.MANIFEST_UNREADABLE
        keys = _citation_keys(provision)
        if not keys or keys & seen_citations:
            return PromotionRefusal.PROVISION_IDENTIFIER_AMBIGUOUS
        seen_citations |= keys
        declared |= keys

    sections_file = _load_json(layout.sections_path)
    if sections_file is None:
        return PromotionRefusal.SECTIONS_UNREADABLE

    extraction = sections_file.get("extraction")
    if not isinstance(extraction, dict) or not isinstance(extraction.get("tool"), dict):
        return PromotionRefusal.EXTRACTION_TOOL_UNRECORDED
    tool = extraction["tool"]
    if not (isinstance(tool.get("implementation"), str) and isinstance(tool.get("version"), str)):
        return PromotionRefusal.EXTRACTION_TOOL_UNRECORDED

    if sections_file.get("source_id") != manifest.get("source_id"):
        return PromotionRefusal.SECTIONS_SOURCE_MISMATCH
    if sections_file.get("source_document_sha256") != recorded_digest:
        return PromotionRefusal.SECTIONS_SOURCE_MISMATCH

    records = sections_file.get("sections")
    if not isinstance(records, list) or not records:
        return PromotionRefusal.SECTIONS_UNREADABLE

    verification_records = sections_file.get("verification_records")
    verified_by: dict[str, Any] = (
        verification_records if isinstance(verification_records, dict) else {}
    )

    seen_sections: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            return PromotionRefusal.SECTIONS_UNREADABLE
        identifier = record.get("identifier")
        text = record.get("text")
        digest = record.get("text_sha256")
        if not (isinstance(identifier, str) and isinstance(text, str) and isinstance(digest, str)):
            return PromotionRefusal.SECTIONS_UNREADABLE

        key = _normalise(identifier)
        if key in seen_sections:
            return PromotionRefusal.SECTION_IDENTIFIER_AMBIGUOUS
        seen_sections.add(key)

        if key not in declared:
            return PromotionRefusal.SECTION_NOT_IN_MANIFEST
        if section_text_digest(text) != digest:
            return PromotionRefusal.SECTION_TEXT_HASH_MISMATCH

        if record.get("verified") is True and not _has_verification_record(
            verified_by.get(identifier)
        ):
            return PromotionRefusal.SECTION_VERIFIED_WITHOUT_RECORD

    approval_refusal = _check_owner_approval(layout=layout, manifest=manifest)
    if approval_refusal is not None:
        return approval_refusal

    act = manifest.get("act")
    title = act.get("title") if isinstance(act, dict) else None
    if not isinstance(title, str) or not title.strip():
        return PromotionRefusal.MANIFEST_UNREADABLE
    if _title_already_present(active_root=active_root, title=title):
        return PromotionRefusal.ACT_TITLE_ALREADY_PRESENT

    target = active_root / slug_for_title(title)
    if target.exists():
        return PromotionRefusal.TARGET_ALREADY_EXISTS

    return PromotionPlan(
        layout=layout,
        target_directory=target,
        manifest=manifest,
        sections=sections_file,
    )


def _has_verification_record(record: Any) -> bool:
    """A G2 record must name a person and the document they compared against."""

    return (
        isinstance(record, dict)
        and isinstance(record.get("verified_by"), str)
        and bool(record["verified_by"].strip())
        and isinstance(record.get("verified_against"), str)
        and bool(record["verified_against"].strip())
        and isinstance(record.get("verified_on"), str)
        and bool(record["verified_on"].strip())
    )


def _check_owner_approval(
    *,
    layout: StagingLayout,
    manifest: dict[str, Any],
) -> PromotionRefusal | None:
    """Gate G1: an owner accepted this exact capture, or promotion refuses."""

    if not layout.approval_path.is_file():
        return PromotionRefusal.OWNER_APPROVAL_MISSING
    approval = _load_json(layout.approval_path)
    if approval is None:
        return PromotionRefusal.OWNER_APPROVAL_MISSING

    if not isinstance(approval.get("approved_by"), str) or not approval["approved_by"].strip():
        return PromotionRefusal.OWNER_APPROVAL_MISSING

    version = manifest.get("version")
    expected = {
        "source_id": manifest.get("source_id"),
        "official_source_url": manifest.get("official_source_url"),
        "version_suffix": version.get("suffix") if isinstance(version, dict) else None,
        "currency_start": version.get("currency_start") if isinstance(version, dict) else None,
        "retrieved_at_utc": manifest.get("retrieved_at_utc"),
        "sha256": manifest.get("sha256"),
    }
    for field, value in expected.items():
        if approval.get(field) != value:
            return PromotionRefusal.OWNER_APPROVAL_MISMATCH
    return None


def _title_already_present(*, active_root: Path, title: str) -> bool:
    """Enforce ADR 0017 I7: one manifest per normalised Act title."""

    if not active_root.is_dir():
        return False
    wanted = _normalise(title)
    for manifest_path in sorted(active_root.rglob("*.manifest.json")):
        existing = _load_json(manifest_path)
        if existing is None:
            continue
        act = existing.get("act")
        existing_title = act.get("title") if isinstance(act, dict) else None
        if isinstance(existing_title, str) and _normalise(existing_title) == wanted:
            return True
    return False


def promote(
    *,
    layout: StagingLayout,
    active_root: Path,
) -> PromotionPlan | PromotionRefusal:
    """Copy a staged source into the active corpus, or refuse and change nothing.

    The precondition check runs first and the active root is written only on a
    plan. A refusal leaves the corpus exactly as it was.
    """

    outcome = check_promotion(layout=layout, active_root=active_root)
    if isinstance(outcome, PromotionRefusal):
        return outcome

    outcome.target_directory.mkdir(parents=True, exist_ok=False)
    for source in (layout.pdf_path, layout.manifest_path, layout.sections_path):
        shutil.copy2(source, outcome.target_directory / source.name)
    return outcome

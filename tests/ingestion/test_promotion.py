"""The promotion gate refuses everything it cannot prove, and writes nothing.

Two refusals here cannot be satisfied by code at all — the owner approval
record (G1) and the human verification record (G2). Those are the point.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from scripts.wa_ingest.extraction import section_text_digest
from scripts.wa_ingest.promotion import (
    PromotionPlan,
    PromotionRefusal,
    check_promotion,
    promote,
)
from scripts.wa_ingest.staging import (
    SourceIdentity,
    StagingLayout,
    stage_source,
    write_json,
)

_PDF = b"%PDF-1.7 synthetic promotion fixture"
_DIGEST = hashlib.sha256(_PDF).hexdigest()
_TEXT = "Synthetic section body."
_URL = "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_s1.html"


def identity() -> SourceIdentity:
    return SourceIdentity(
        act_title="Synthetic Vehicles Act 2012",
        act_number="007 of 2012",
        version_suffix="01-j0-00",
        currency_start=date(2024, 10, 7),
        status_currency="Current",
        status_in_force=True,
        status_date=date(2025, 1, 10),
        official_source_url=_URL,
        retrieved_at=datetime(2026, 8, 11, 10, 27, 3, tzinfo=UTC),
    )


def approval_for(manifest: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    record = {
        "approved_by": "owner@example.test",
        "source_id": manifest["source_id"],
        "official_source_url": manifest["official_source_url"],
        "version_suffix": manifest["version"]["suffix"],
        "currency_start": manifest["version"]["currency_start"],
        "retrieved_at_utc": manifest["retrieved_at_utc"],
        "sha256": manifest["sha256"],
    }
    record.update(overrides)
    return record


def sections_for(manifest: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source_id": manifest["source_id"],
        "source_document_sha256": manifest["sha256"],
        "extraction": {
            "tool": {"implementation": "poppler-utils", "version": "24.02.0"},
            "arguments": ["-layout"],
        },
        "sections": [
            {
                "identifier": "s 55",
                "heading": "Heading",
                "text": _TEXT,
                "text_sha256": section_text_digest(_TEXT),
                "verified": False,
            }
        ],
    }
    payload.update(overrides)
    return payload


def staged(tmp_path: Path, *, provisions: Any = None, **section_overrides: Any) -> StagingLayout:
    """A complete, promotable staging directory unless a test breaks one part."""

    downloaded = tmp_path / "downloaded.pdf"
    downloaded.write_bytes(_PDF)
    layout = stage_source(
        identity=identity(),
        downloaded_pdf=downloaded,
        staging_root=tmp_path / "staging",
    )
    manifest = json.loads(layout.manifest_path.read_text(encoding="utf-8"))
    manifest["provisions"] = (
        provisions
        if provisions is not None
        else [{"identifier": "s 55", "pinpoint": "section 55", "heading": "Heading"}]
    )
    write_json(layout.manifest_path, manifest)
    write_json(layout.sections_path, sections_for(manifest, **section_overrides))
    write_json(layout.approval_path, approval_for(manifest))
    return layout


def active(tmp_path: Path) -> Path:
    root = tmp_path / "active"
    root.mkdir(exist_ok=True)
    return root


def refusal(layout: StagingLayout, root: Path) -> PromotionRefusal | PromotionPlan:
    return check_promotion(layout=layout, active_root=root)


# ---------------------------------------------------------------------------
# The happy path exists, so every refusal below means something
# ---------------------------------------------------------------------------


def test_a_complete_staged_source_is_promotable(tmp_path: Path) -> None:
    outcome = refusal(staged(tmp_path), active(tmp_path))
    assert isinstance(outcome, PromotionPlan)
    assert outcome.target_directory.name == "synthetic_vehicles_act_2012"


def test_promotion_copies_all_three_files(tmp_path: Path) -> None:
    root = active(tmp_path)
    outcome = promote(layout=staged(tmp_path), active_root=root)
    assert isinstance(outcome, PromotionPlan)
    names = sorted(p.name for p in outcome.target_directory.iterdir())
    assert names == [
        "synthetic_vehicles_act_2012_consolidated_01-j0-00.manifest.json",
        "synthetic_vehicles_act_2012_consolidated_01-j0-00.pdf",
        "synthetic_vehicles_act_2012_consolidated_01-j0-00.sections.json",
    ]
    assert (outcome.target_directory / names[1]).read_bytes() == _PDF


def test_the_owner_approval_record_is_not_copied_into_the_corpus(tmp_path: Path) -> None:
    outcome = promote(layout=staged(tmp_path), active_root=active(tmp_path))
    assert isinstance(outcome, PromotionPlan)
    assert not (outcome.target_directory / "OWNER_APPROVAL.json").exists()


# ---------------------------------------------------------------------------
# Gate G1 — owner approval
# ---------------------------------------------------------------------------


def test_no_approval_record_refuses(tmp_path: Path) -> None:
    layout = staged(tmp_path)
    layout.approval_path.unlink()
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.OWNER_APPROVAL_MISSING


def test_an_unsigned_approval_refuses(tmp_path: Path) -> None:
    layout = staged(tmp_path)
    manifest = json.loads(layout.manifest_path.read_text(encoding="utf-8"))
    write_json(layout.approval_path, approval_for(manifest, approved_by="  "))
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.OWNER_APPROVAL_MISSING


@pytest.mark.parametrize(
    "field",
    [
        "source_id",
        "official_source_url",
        "version_suffix",
        "currency_start",
        "retrieved_at_utc",
        "sha256",
    ],
)
def test_an_approval_for_a_different_capture_refuses(tmp_path: Path, field: str) -> None:
    """Approving one version must not silently approve another."""

    layout = staged(tmp_path)
    manifest = json.loads(layout.manifest_path.read_text(encoding="utf-8"))
    write_json(layout.approval_path, approval_for(manifest, **{field: "something-else"}))
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.OWNER_APPROVAL_MISMATCH


# ---------------------------------------------------------------------------
# Gate G2 — human verification
# ---------------------------------------------------------------------------


def test_a_verified_section_without_a_record_refuses(tmp_path: Path) -> None:
    """A true flag with nobody's name against it is exactly what G2 forbids."""

    layout = staged(tmp_path)
    payload = json.loads(layout.sections_path.read_text(encoding="utf-8"))
    payload["sections"][0]["verified"] = True
    write_json(layout.sections_path, payload)
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.SECTION_VERIFIED_WITHOUT_RECORD


def test_a_verified_section_with_a_complete_record_is_accepted(tmp_path: Path) -> None:
    layout = staged(tmp_path)
    payload = json.loads(layout.sections_path.read_text(encoding="utf-8"))
    payload["sections"][0]["verified"] = True
    payload["verification_records"] = {
        "s 55": {
            "verified_by": "A Person",
            "verified_against": "official consolidated PDF 01-j0-00",
            "verified_on": "2026-09-10",
        }
    }
    write_json(layout.sections_path, payload)
    assert isinstance(refusal(layout, active(tmp_path)), PromotionPlan)


@pytest.mark.parametrize("missing", ["verified_by", "verified_against", "verified_on"])
def test_an_incomplete_verification_record_refuses(tmp_path: Path, missing: str) -> None:
    layout = staged(tmp_path)
    payload = json.loads(layout.sections_path.read_text(encoding="utf-8"))
    payload["sections"][0]["verified"] = True
    record = {
        "verified_by": "A Person",
        "verified_against": "official PDF",
        "verified_on": "2026-09-10",
    }
    del record[missing]
    payload["verification_records"] = {"s 55": record}
    write_json(layout.sections_path, payload)
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.SECTION_VERIFIED_WITHOUT_RECORD


def test_unverified_sections_need_no_record(tmp_path: Path) -> None:
    """The default path stays open: false flags promote without ceremony."""

    assert isinstance(refusal(staged(tmp_path), active(tmp_path)), PromotionPlan)


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------


def test_a_tampered_staged_file_refuses(tmp_path: Path) -> None:
    layout = staged(tmp_path)
    layout.pdf_path.write_bytes(b"tampered")
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.MANIFEST_DIGEST_MISMATCH


def test_a_sections_file_naming_another_source_refuses(tmp_path: Path) -> None:
    layout = staged(tmp_path, source_id="wa_legislation:other:consolidated:01-a0-00")
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.SECTIONS_SOURCE_MISMATCH


def test_a_sections_file_naming_another_document_refuses(tmp_path: Path) -> None:
    layout = staged(tmp_path, source_document_sha256="0" * 64)
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.SECTIONS_SOURCE_MISMATCH


def test_a_section_whose_digest_disagrees_refuses(tmp_path: Path) -> None:
    layout = staged(tmp_path)
    payload = json.loads(layout.sections_path.read_text(encoding="utf-8"))
    payload["sections"][0]["text_sha256"] = "0" * 64
    write_json(layout.sections_path, payload)
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.SECTION_TEXT_HASH_MISMATCH


def test_a_section_the_manifest_never_declared_refuses(tmp_path: Path) -> None:
    layout = staged(tmp_path)
    payload = json.loads(layout.sections_path.read_text(encoding="utf-8"))
    payload["sections"][0]["identifier"] = "s 999"
    payload["sections"][0]["text_sha256"] = section_text_digest(_TEXT)
    write_json(layout.sections_path, payload)
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.SECTION_NOT_IN_MANIFEST


def test_duplicate_section_identifiers_refuse(tmp_path: Path) -> None:
    layout = staged(tmp_path)
    payload = json.loads(layout.sections_path.read_text(encoding="utf-8"))
    payload["sections"].append(dict(payload["sections"][0]))
    write_json(layout.sections_path, payload)
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.SECTION_IDENTIFIER_AMBIGUOUS


def test_an_unrecorded_extraction_tool_refuses(tmp_path: Path) -> None:
    layout = staged(tmp_path, extraction={"arguments": ["-layout"]})
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.EXTRACTION_TOOL_UNRECORDED


# ---------------------------------------------------------------------------
# ADR 0017 invariants I7, I9, I11
# ---------------------------------------------------------------------------


def test_an_empty_provision_list_refuses(tmp_path: Path) -> None:
    assert refusal(staged(tmp_path, provisions=[]), active(tmp_path)) is (
        PromotionRefusal.PROVISIONS_EMPTY
    )


def test_duplicate_provision_identifiers_refuse(tmp_path: Path) -> None:
    layout = staged(
        tmp_path,
        provisions=[
            {"identifier": "s 55", "pinpoint": "section 55"},
            {"identifier": "S  55", "pinpoint": "section 55"},
        ],
    )
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.PROVISION_IDENTIFIER_AMBIGUOUS


def test_a_pinpoint_colliding_with_another_identifier_refuses(tmp_path: Path) -> None:
    """The E0-A cross-field collision, caught before the corpus ever sees it."""

    layout = staged(
        tmp_path,
        provisions=[
            {"identifier": "s 55", "pinpoint": "section 55"},
            {"identifier": "section 55", "pinpoint": "section 55A"},
        ],
    )
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.PROVISION_IDENTIFIER_AMBIGUOUS


def test_a_second_manifest_for_the_same_act_title_refuses(tmp_path: Path) -> None:
    """ADR 0017 I7: one manifest per Act title in the active root."""

    root = active(tmp_path)
    existing = root / "already_here"
    existing.mkdir()
    write_json(
        existing / "x.manifest.json",
        {"act": {"title": "Synthetic  VEHICLES   Act 2012"}},
    )
    assert refusal(staged(tmp_path), root) is PromotionRefusal.ACT_TITLE_ALREADY_PRESENT


def test_an_existing_target_directory_refuses(tmp_path: Path) -> None:
    root = active(tmp_path)
    (root / "synthetic_vehicles_act_2012").mkdir()
    assert refusal(staged(tmp_path), root) is PromotionRefusal.TARGET_ALREADY_EXISTS


# ---------------------------------------------------------------------------
# Completeness, and the no-write guarantee
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("removed", ["pdf_path", "manifest_path", "sections_path"])
def test_an_incomplete_staging_directory_refuses(tmp_path: Path, removed: str) -> None:
    layout = staged(tmp_path)
    getattr(layout, removed).unlink()
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.STAGING_INCOMPLETE


def test_an_unreadable_manifest_refuses(tmp_path: Path) -> None:
    layout = staged(tmp_path)
    layout.manifest_path.write_text("{ not json", encoding="utf-8")
    assert refusal(layout, active(tmp_path)) is PromotionRefusal.MANIFEST_UNREADABLE


def test_a_refusal_writes_nothing_into_the_active_corpus(tmp_path: Path) -> None:
    root = active(tmp_path)
    layout = staged(tmp_path)
    layout.approval_path.unlink()

    outcome = promote(layout=layout, active_root=root)

    assert outcome is PromotionRefusal.OWNER_APPROVAL_MISSING
    assert list(root.iterdir()) == []

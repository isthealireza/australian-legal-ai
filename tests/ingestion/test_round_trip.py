"""What the pipeline emits, the runtime accepts.

The staging tooling and the research module agree on a file format but share no
code — the tooling deliberately does not import `legal_ai`. That makes the
agreement a convention, and a convention nothing checks is one that drifts.

This module closes the loop on a synthetic source: stage, declare, extract,
approve, promote, then read the result back through `RecordedWaCorpus` and
`WaResearchService`. No network, no clock, no database, no external binary, and
the recorded corpus is never touched.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from scripts.wa_ingest.extraction import (
    POPPLER,
    ExtractionTool,
    SectionDraft,
    build_sections_file,
)
from scripts.wa_ingest.promotion import PromotionPlan, PromotionRefusal, promote
from scripts.wa_ingest.staging import (
    SourceIdentity,
    StagingLayout,
    stage_source,
    write_json,
)

from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.models import ResearchQuery
from legal_ai.research.sections import verify_section
from legal_ai.research.service import ResearchRefused, ResearchValidated, WaResearchService
from legal_ai.research.types import LegalStatus, ResearchRefusalCode
from tests.support.research_audit import InMemoryResearchAuditSink

_ACT = "Synthetic Round Trip Act 2012"
_PDF = b"%PDF-1.7 synthetic round-trip fixture\n" + b"x" * 2048
_TOOL = ExtractionTool(implementation=POPPLER, version="24.02.0")


def _identity() -> SourceIdentity:
    return SourceIdentity(
        act_title=_ACT,
        act_number="007 of 2012",
        assent_date=date(2012, 5, 21),
        version_suffix="01-j0-00",
        currency_start=date(2024, 10, 7),
        currency_end="current",
        status_currency="Current",
        status_in_force=True,
        status_date=date(2025, 1, 10),
        official_source_url=(
            "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_s1.html"
        ),
        retrieved_at=datetime(2026, 9, 12, 1, 0, 0, tzinfo=UTC),
    )


def _fully_staged(tmp_path: Path, staging_root: Path) -> StagingLayout:
    """Stage, declare provisions, extract and approve. Everything but promote."""

    downloaded = tmp_path / f"{staging_root.name}.pdf"
    downloaded.write_bytes(_PDF)

    layout = stage_source(
        identity=_identity(),
        downloaded_pdf=downloaded,
        staging_root=staging_root,
    )

    manifest = json.loads(layout.manifest_path.read_text(encoding="utf-8"))
    manifest["provisions"] = [
        {"identifier": "s 12", "pinpoint": "section 12", "heading": "Heading A"},
        {"identifier": "s 13", "pinpoint": "section 13", "heading": "Heading B"},
    ]
    write_json(layout.manifest_path, manifest)

    write_json(
        layout.sections_path,
        build_sections_file(
            source_id=manifest["source_id"],
            source_document_sha256=manifest["sha256"],
            tool=_TOOL,
            drafts=[
                SectionDraft(identifier="s 12", heading="Heading A", text="Body of twelve."),
                SectionDraft(identifier="s 13", heading="Heading B", text="Body of thirteen."),
            ],
        ),
    )

    write_json(
        layout.approval_path,
        {
            "approved_by": "round-trip-test",
            "source_id": manifest["source_id"],
            "official_source_url": manifest["official_source_url"],
            "version_suffix": manifest["version"]["suffix"],
            "currency_start": manifest["version"]["currency_start"],
            "retrieved_at_utc": manifest["retrieved_at_utc"],
            "sha256": manifest["sha256"],
        },
    )

    return layout


def _promoted_corpus(tmp_path: Path) -> Path:
    """Run the whole pipeline and return the active root it promoted into."""

    active = tmp_path / "active"
    active.mkdir()
    outcome = promote(
        layout=_fully_staged(tmp_path, tmp_path / "staging"),
        active_root=active,
    )
    assert isinstance(outcome, PromotionPlan), outcome
    return active


def _query(**overrides: str) -> ResearchQuery:
    fields = {
        "jurisdiction": "WA",
        "act_title": _ACT,
        "provision_identifier": "s 12",
        "pinpoint": "section 12",
    }
    fields.update(overrides)
    return ResearchQuery(**fields)


def _service(active: Path) -> WaResearchService:
    return WaResearchService(
        corpus=RecordedWaCorpus(active),
        audit_sink=InMemoryResearchAuditSink(),
    )


def test_a_promoted_source_validates_through_the_runtime(tmp_path: Path) -> None:
    """The manifest the tooling writes is one the research module accepts."""

    result = _service(_promoted_corpus(tmp_path)).research(_query())

    assert isinstance(result, ResearchValidated)
    packet = result.packet
    assert packet.act.title == _ACT
    assert packet.act.act_number == "007 of 2012"
    assert packet.source_version == "01-j0-00"
    assert packet.compilation_date == date(2024, 10, 7)
    assert packet.status_date == date(2025, 1, 10)
    assert packet.legal_status is LegalStatus.IN_FORCE
    assert packet.provision_identifier == "s 12"
    assert packet.pinpoint == "section 12"


def test_the_generated_digest_survives_promotion(tmp_path: Path) -> None:
    result = _service(_promoted_corpus(tmp_path)).research(_query())
    assert isinstance(result, ResearchValidated)
    assert result.packet.source_content == _PDF


def test_both_declared_provisions_resolve_and_stay_distinct(tmp_path: Path) -> None:
    service = _service(_promoted_corpus(tmp_path))
    twelve = service.research(_query())
    thirteen = service.research(_query(provision_identifier="s 13", pinpoint="section 13"))

    assert isinstance(twelve, ResearchValidated)
    assert isinstance(thirteen, ResearchValidated)
    assert twelve.packet.source_id == thirteen.packet.source_id
    assert twelve.packet.provision_identifier != thirteen.packet.provision_identifier


def test_an_undeclared_provision_refuses(tmp_path: Path) -> None:
    result = _service(_promoted_corpus(tmp_path)).research(
        _query(provision_identifier="s 99", pinpoint="section 99")
    )
    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.CITATION_NOT_FOUND


def test_the_e0a_parent_binding_survives_promotion(tmp_path: Path) -> None:
    """The sections file the tooling wrote satisfies E0-A's binding check."""

    source = RecordedWaCorpus(_promoted_corpus(tmp_path)).select(_query())
    assert source is not None
    assert source.sections_source_id == source.source_id
    assert source.sections_source_document_sha256 == source.sha256


def test_promoted_sections_are_refused_until_a_human_verifies_them(tmp_path: Path) -> None:
    """The whole pipeline cannot produce usable drafting evidence. Gate G2."""

    source = RecordedWaCorpus(_promoted_corpus(tmp_path)).select(_query())
    assert source is not None
    for identifier in ("s 12", "s 13"):
        assert verify_section(source=source, identifier=identifier) is (
            ResearchRefusalCode.SECTION_NOT_VERIFIED
        )


def test_promoting_the_same_act_twice_refuses(tmp_path: Path) -> None:
    """ADR 0017 I7 holds against a real promoted source, not just a stub."""

    active = _promoted_corpus(tmp_path)

    # A second capture that is complete in every other way, so the title check
    # is what refuses rather than an incomplete staging directory.
    second = _fully_staged(tmp_path, tmp_path / "staging2")

    assert promote(layout=second, active_root=active) is (
        PromotionRefusal.ACT_TITLE_ALREADY_PRESENT
    )

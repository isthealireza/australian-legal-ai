"""Bounded staging checks for the official WALW vehicles regulations artifact."""

from __future__ import annotations

import hashlib
from pathlib import Path

from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.models import ResearchQuery
from legal_ai.research.service import ResearchRefused, WaResearchService
from legal_ai.research.types import ResearchRefusalCode
from tests.support.research_audit import InMemoryResearchAuditSink

_ROOT = Path(__file__).parents[1] / "fixtures" / "wa_legislation"
_STAGED = _ROOT / "road_traffic_vehicles_regulations_2014"
_PDF = _STAGED / "road_traffic_vehicles_regulations_2014_consolidated_01-at0-00.pdf"
_TITLE = "Road Traffic (Vehicles) Regulations 2014"
_SOURCE_ID = "wa_legislation:road_traffic_vehicles_regulations_2014:consolidated:01-at0-00"
_SHA256 = "912d05faaf5a1f1fd0b0f88751caa30fac36202ae484e6777336c5bb6b8e32af"


def test_staged_artifact_is_exact_and_selectable() -> None:
    content = _PDF.read_bytes()
    assert len(content) == 2_149_832
    assert hashlib.sha256(content).hexdigest() == _SHA256

    source = RecordedWaCorpus(_ROOT).select(
        ResearchQuery(
            jurisdiction="WA",
            act_title=_TITLE,
            provision_identifier="regulation 1",
            pinpoint="regulation 1",
        )
    )
    assert source is not None
    assert source.source_id == _SOURCE_ID
    assert source.source_version == "01-at0-00"
    assert source.compilation_date == "2026-07-01"
    assert source.status_currency == "Current"
    assert source.status_in_force is True
    assert source.sha256 == _SHA256
    assert source.provisions == ()


def test_staged_source_refuses_until_provisions_are_deterministically_extracted() -> None:
    sink = InMemoryResearchAuditSink()
    result = WaResearchService(
        corpus=RecordedWaCorpus(_ROOT), audit_sink=sink
    ).research(
        ResearchQuery(
            jurisdiction="WA",
            act_title=_TITLE,
            provision_identifier="regulation 1",
            pinpoint="regulation 1",
        )
    )
    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.CITATION_NOT_FOUND

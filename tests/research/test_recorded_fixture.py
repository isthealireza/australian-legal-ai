"""End-to-end integration over the durable recorded WA fixture on `main`.

These tests read the committed Road Traffic Act 1974 (WA) fixture only. They
never modify it, never retrieve a new copy, and never touch the network.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest

from legal_ai.research.audit import ResearchAuditSink
from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.service import (
    ResearchRefused,
    ResearchTerminated,
    ResearchValidated,
    WaResearchService,
)
from legal_ai.research.types import (
    LegalStatus,
    ResearchAuditResult,
    ResearchOutcome,
    ResearchRefusalCode,
    ResearchTerminalCode,
)
from tests.research.conftest import (
    RECORDED_ACT_TITLE,
    RECORDED_FIXTURE_ROOT,
    RECORDED_SHA256,
    RECORDED_SOURCE_ID,
    recorded_query,
)
from tests.support.research_audit import (
    FailingResearchAuditSink,
    InMemoryResearchAuditSink,
    UnavailableResearchAuditSink,
)

_FIXTURE_PDF = (
    RECORDED_FIXTURE_ROOT
    / "road_traffic_act_1974"
    / "road_traffic_act_1974_consolidated_14-t0-00.pdf"
)
_OFFICIAL_URL = (
    "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a703.html&view=consolidated"
)
_PROVISIONS = [
    (
        "s 55",
        "section 55",
        "Driver in incident occasioning property damage to stop and give information",
    ),
    (
        "s 56",
        "section 56",
        "Driver in incident occasioning bodily harm or property damage to report incident to "
        "police",
    ),
]


def _service(sink: ResearchAuditSink | None) -> WaResearchService:
    return WaResearchService(corpus=RecordedWaCorpus(RECORDED_FIXTURE_ROOT), audit_sink=sink)


def test_recorded_fixture_bytes_are_unmodified() -> None:
    assert hashlib.sha256(_FIXTURE_PDF.read_bytes()).hexdigest() == RECORDED_SHA256


@pytest.mark.parametrize(
    ("identifier", "pinpoint", "heading"), _PROVISIONS, ids=["section-55", "section-56"]
)
def test_recorded_provision_yields_a_complete_validated_packet(
    identifier: str, pinpoint: str, heading: str
) -> None:
    sink = InMemoryResearchAuditSink()
    service = _service(sink)

    result = service.research(recorded_query(provision_identifier=identifier, pinpoint=pinpoint))

    assert isinstance(result, ResearchValidated)
    packet = result.packet
    assert packet.source_id == RECORDED_SOURCE_ID
    assert packet.source_system == "wa_legislation"
    assert packet.jurisdiction == "WA"
    assert packet.official_source_url == _OFFICIAL_URL
    assert packet.act.title == RECORDED_ACT_TITLE
    assert packet.act.jurisdiction == "WA"
    assert packet.act.act_number == "059 of 1974"
    assert packet.provision_identifier == identifier
    assert packet.pinpoint == pinpoint
    assert packet.provision_heading == heading
    assert packet.source_version == "14-t0-00"
    assert packet.compilation_date == date(2025, 1, 10)
    assert packet.legal_status is LegalStatus.IN_FORCE
    assert packet.status_date == date(2025, 1, 10)
    assert packet.retrieved_at == datetime(2026, 8, 11, 10, 27, 3, tzinfo=UTC)
    assert packet.source_content == _FIXTURE_PDF.read_bytes()
    assert packet.sha256 == RECORDED_SHA256
    assert packet.audit_result is ResearchAuditResult.RECORDED


def test_packet_sha256_is_recomputed_against_the_exact_fixture_content() -> None:
    result = _service(InMemoryResearchAuditSink()).research(recorded_query())

    assert isinstance(result, ResearchValidated)
    assert result.packet.sha256 == hashlib.sha256(result.packet.source_content).hexdigest()
    assert result.packet.sha256 == RECORDED_SHA256


def test_both_recorded_provisions_share_the_same_official_source_and_digest() -> None:
    service = _service(InMemoryResearchAuditSink())

    packets = []
    for identifier, pinpoint, _ in _PROVISIONS:
        result = service.research(
            recorded_query(provision_identifier=identifier, pinpoint=pinpoint)
        )
        assert isinstance(result, ResearchValidated)
        packets.append(result.packet)

    assert {packet.sha256 for packet in packets} == {RECORDED_SHA256}
    assert {packet.official_source_url for packet in packets} == {_OFFICIAL_URL}
    assert {packet.provision_identifier for packet in packets} == {"s 55", "s 56"}


def test_validated_run_records_exactly_one_audit_event() -> None:
    sink = InMemoryResearchAuditSink()

    result = _service(sink).research(recorded_query())

    assert isinstance(result, ResearchValidated)
    assert len(sink.events) == 1
    assert sink.events[0].outcome is ResearchOutcome.VALIDATED
    assert sink.events[0].source_id == RECORDED_SOURCE_ID
    assert sink.events[0].sha256 == RECORDED_SHA256


@pytest.mark.parametrize("identifier", ["s 54", "s 57", "s 55A", "s 999"])
def test_provisions_outside_the_recorded_pinpoints_refuse(identifier: str) -> None:
    result = _service(InMemoryResearchAuditSink()).research(
        recorded_query(provision_identifier=identifier, pinpoint="section 55")
    )

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.CITATION_NOT_FOUND


def test_pinpoint_mismatch_against_the_recorded_provision_refuses() -> None:
    result = _service(InMemoryResearchAuditSink()).research(
        recorded_query(provision_identifier="s 55", pinpoint="section 56")
    )

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.PINPOINT_MISMATCH


def test_out_of_corpus_act_refuses() -> None:
    result = _service(InMemoryResearchAuditSink()).research(
        recorded_query(act_title="Sale of Goods Act 1895")
    )

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.RETRIEVAL_MISSING


def test_cross_jurisdiction_request_against_the_recorded_wa_fixture_refuses() -> None:
    result = _service(InMemoryResearchAuditSink()).research(recorded_query(jurisdiction="NSW"))

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.JURISDICTION_MISMATCH


@pytest.mark.parametrize(
    "make_sink",
    [
        lambda: None,
        lambda: UnavailableResearchAuditSink(),
        lambda: FailingResearchAuditSink(),
    ],
    ids=["absent", "unavailable", "failing"],
)
def test_audit_sink_failure_returns_no_packet_for_the_recorded_fixture(
    make_sink: Callable[[], ResearchAuditSink | None],
) -> None:
    result = _service(make_sink()).research(recorded_query())

    assert isinstance(result, ResearchTerminated)
    assert result.code is ResearchTerminalCode.AUDIT_SINK_UNAVAILABLE
    assert not hasattr(result, "packet")
    assert RECORDED_SHA256 not in repr(result)


def test_repeated_execution_over_the_recorded_fixture_is_deterministic() -> None:
    sink = InMemoryResearchAuditSink()
    service = _service(sink)

    packets = []
    for _ in range(3):
        result = service.research(recorded_query())
        assert isinstance(result, ResearchValidated)
        packets.append(result.packet)

    assert packets[0] == packets[1] == packets[2]
    assert len({packet.sha256 for packet in packets}) == 1
    assert len(sink.events) == 3
    assert len({event.source_id for event in sink.events}) == 1


def test_a_fresh_corpus_instance_produces_an_identical_packet() -> None:
    first = _service(InMemoryResearchAuditSink()).research(recorded_query())
    second = _service(InMemoryResearchAuditSink()).research(recorded_query())

    assert isinstance(first, ResearchValidated)
    assert isinstance(second, ResearchValidated)
    assert first.packet == second.packet

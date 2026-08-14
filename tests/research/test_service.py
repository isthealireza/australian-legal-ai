"""Unit tests for the fail-closed WA research service and its audit contract."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import pytest

from legal_ai.research.audit import ResearchAuditSink
from legal_ai.research.models import RecordedWaSource
from legal_ai.research.service import (
    ResearchRefused,
    ResearchResult,
    ResearchTerminated,
    ResearchValidated,
    WaResearchService,
)
from legal_ai.research.types import (
    ResearchOutcome,
    ResearchRefusalCode,
    ResearchTerminalCode,
)
from tests.research.conftest import (
    SYNTHETIC_CONTENT,
    SYNTHETIC_SHA256,
    StubCorpus,
    UnreadableCorpus,
    query,
    recorded_source,
)
from tests.support.research_audit import (
    FailingResearchAuditSink,
    InMemoryResearchAuditSink,
    UnavailableResearchAuditSink,
)

_REFUSING_SOURCES = [
    ("source_system", {"source_system": "federal_register"}),
    ("jurisdiction", {"jurisdiction": "NSW"}),
    ("host", {"official_source_url": "https://legislation.nsw.gov.au/law.html"}),
    ("scheme", {"official_source_url": "http://www.legislation.wa.gov.au/law.html"}),
    ("version", {"source_version": None, "compilation_date": None}),
    ("status", {"status_currency": "UNKNOWN"}),
    ("status_date", {"status_date": "2026-08-12"}),
    ("field", {"source_id": None}),
    ("hash", {"source_content": b"tampered"}),
]


def _service(
    *sources: RecordedWaSource,
    sink: ResearchAuditSink | None = None,
) -> WaResearchService:
    return WaResearchService(corpus=StubCorpus(*sources), audit_sink=sink)


def test_validated_result_is_audited_before_it_is_returned() -> None:
    sink = InMemoryResearchAuditSink()
    service = _service(recorded_source(), sink=sink)

    result = service.research(query())

    assert isinstance(result, ResearchValidated)
    assert result.packet.source_content == SYNTHETIC_CONTENT
    assert result.packet.sha256 == SYNTHETIC_SHA256
    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.outcome is ResearchOutcome.VALIDATED
    assert event.refusal_code is None
    assert event.source_id == result.packet.source_id
    assert event.sha256 == result.packet.sha256


def test_ordinary_refusal_is_audited_and_carries_no_citation() -> None:
    sink = InMemoryResearchAuditSink()
    service = _service(recorded_source(), sink=sink)

    result = service.research(query(provision_identifier="s 99"))

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.CITATION_NOT_FOUND
    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.outcome is ResearchOutcome.REFUSED
    assert event.refusal_code is ResearchRefusalCode.CITATION_NOT_FOUND
    assert event.source_id is None
    assert event.sha256 is None
    assert event.requested_provision_identifier == "s 99"


def test_absent_audit_sink_is_terminal_and_returns_no_packet() -> None:
    service = _service(recorded_source(), sink=None)

    result = service.research(query())

    assert isinstance(result, ResearchTerminated)
    assert result.code is ResearchTerminalCode.AUDIT_SINK_UNAVAILABLE
    assert not hasattr(result, "packet")


def test_unavailable_audit_sink_is_terminal_and_records_nothing() -> None:
    sink = UnavailableResearchAuditSink()
    service = _service(recorded_source(), sink=sink)

    result = service.research(query())

    assert isinstance(result, ResearchTerminated)
    assert result.code is ResearchTerminalCode.AUDIT_SINK_UNAVAILABLE
    assert sink.events == []


def test_failing_audit_sink_is_terminal_on_the_validated_path() -> None:
    sink = FailingResearchAuditSink()
    service = _service(recorded_source(), sink=sink)

    result = service.research(query())

    assert isinstance(result, ResearchTerminated)
    assert sink.events == []


@pytest.mark.parametrize(
    "make_sink",
    [
        lambda: None,
        lambda: UnavailableResearchAuditSink(),
        lambda: FailingResearchAuditSink(),
    ],
    ids=["absent", "unavailable", "failing"],
)
def test_audit_failure_on_the_refusal_path_is_also_terminal(
    make_sink: Callable[[], ResearchAuditSink | None],
) -> None:
    service = _service(recorded_source(), sink=make_sink())

    result = service.research(query(provision_identifier="s 99"))

    assert isinstance(result, ResearchTerminated)
    assert result.code is ResearchTerminalCode.AUDIT_SINK_UNAVAILABLE


def test_terminal_result_never_claims_an_audit_event_was_emitted() -> None:
    sink = FailingResearchAuditSink()
    service = _service(recorded_source(), sink=sink)

    result = service.research(query())

    assert isinstance(result, ResearchTerminated)
    assert [field.name for field in dataclasses.fields(result)] == ["code"]


@pytest.mark.parametrize(
    ("label", "overrides"),
    _REFUSING_SOURCES,
    ids=[case[0] for case in _REFUSING_SOURCES],
)
def test_no_refusal_emits_a_partial_packet_or_a_citation(
    label: str, overrides: dict[str, object]
) -> None:
    del label
    sink = InMemoryResearchAuditSink()
    service = _service(recorded_source(**overrides), sink=sink)

    result = service.research(query())

    assert isinstance(result, ResearchRefused)
    assert [field.name for field in dataclasses.fields(result)] == ["code"]
    assert not hasattr(result, "packet")
    rendered = repr(result)
    assert "wa_legislation:" not in rendered
    assert "legislation.wa.gov.au" not in rendered
    assert SYNTHETIC_SHA256 not in rendered


def test_cross_jurisdiction_query_refuses_before_any_retrieval() -> None:
    sink = InMemoryResearchAuditSink()
    service = WaResearchService(corpus=UnreadableCorpus(), audit_sink=sink)

    result = service.research(query(jurisdiction="NSW"))

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.JURISDICTION_MISMATCH


def test_out_of_corpus_request_refuses_as_missing_retrieval() -> None:
    sink = InMemoryResearchAuditSink()
    service = _service(recorded_source(), sink=sink)

    result = service.research(query(act_title="Sale of Goods Act 1895"))

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.RETRIEVAL_MISSING


def test_unreadable_recorded_corpus_refuses_as_missing_retrieval() -> None:
    sink = InMemoryResearchAuditSink()
    service = WaResearchService(corpus=UnreadableCorpus(), audit_sink=sink)

    result = service.research(query())

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.RETRIEVAL_MISSING


def test_non_unique_selection_refuses_rather_than_guessing() -> None:
    sink = InMemoryResearchAuditSink()
    service = _service(recorded_source(), recorded_source(source_id="other"), sink=sink)

    result = service.research(query())

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.SELECTION_AMBIGUOUS


def _summary(result: ResearchResult) -> tuple[str, str]:
    if isinstance(result, ResearchValidated):
        return ("VALIDATED", result.packet.sha256)
    return (type(result).__name__, result.code.value)


def test_repeated_execution_is_deterministic() -> None:
    sink = InMemoryResearchAuditSink()
    service = _service(recorded_source(), sink=sink)
    requests = [query(), query(provision_identifier="s 99"), query(jurisdiction="NSW")]

    first = [_summary(service.research(request)) for request in requests]
    second = [_summary(service.research(request)) for request in requests]

    assert first == second
    assert len(sink.events) == 6
    assert [event.outcome for event in sink.events[:3]] == [
        event.outcome for event in sink.events[3:]
    ]

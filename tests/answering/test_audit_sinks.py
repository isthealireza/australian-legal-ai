"""Audit sinks must persist every event and fail loudly when they cannot."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from legal_ai.answering.audit_sinks import JsonlResearchAuditSink, LoggingResearchAuditSink
from legal_ai.research.audit import ResearchAuditEvent
from legal_ai.research.errors import ResearchAuditSinkUnavailable
from legal_ai.research.types import ResearchOutcome, ResearchRefusalCode


def _refusal_event() -> ResearchAuditEvent:
    return ResearchAuditEvent(
        outcome=ResearchOutcome.REFUSED,
        refusal_code=ResearchRefusalCode.RETRIEVAL_MISSING,
        requested_jurisdiction="WA",
        requested_act_title="An Act That Is Not Indexed 2020",
        requested_provision_identifier="s 1",
        requested_pinpoint="section 1",
    )


def test_jsonl_sink_appends_one_line_per_event(tmp_path: Path) -> None:
    path = tmp_path / "audit" / "research.jsonl"
    sink = JsonlResearchAuditSink(path)
    sink.record(_refusal_event())
    sink.record(_refusal_event())

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["refusal_code"] == "RETRIEVAL_MISSING"


def test_jsonl_sink_refusal_records_no_citation(tmp_path: Path) -> None:
    path = tmp_path / "research.jsonl"
    JsonlResearchAuditSink(path).record(_refusal_event())
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert record["source_id"] is None
    assert record["sha256"] is None


def test_jsonl_sink_raises_when_the_path_is_unwritable(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    with pytest.raises(ResearchAuditSinkUnavailable):
        JsonlResearchAuditSink(blocker / "nested" / "research.jsonl")


def test_logging_sink_emits_the_event(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="legal_ai.research.audit"):
        LoggingResearchAuditSink().record(_refusal_event())
    assert "RETRIEVAL_MISSING" in caplog.text

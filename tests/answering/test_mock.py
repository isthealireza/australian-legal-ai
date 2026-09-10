"""The mock adapter must produce output that validates by construction."""

from __future__ import annotations

from legal_ai.answering.mock import MockAnswerModel
from legal_ai.answering.models import GroundedAnswerRequest
from legal_ai.answering.validation import validate_draft
from tests.answering.conftest import build_packet


def _request(packet_heading: str | None) -> tuple[GroundedAnswerRequest, object]:
    packet = build_packet()
    request = GroundedAnswerRequest(
        question="What must a driver do?",
        source_id=packet.source_id,
        act_title=packet.act.title,
        provision_identifier=packet.provision_identifier,
        pinpoint=packet.pinpoint,
        provision_heading=packet_heading,
        source_version=packet.source_version,
        compilation_date=packet.compilation_date,
        official_source_url=packet.official_source_url,
        sha256=packet.sha256,
        source_content=packet.source_content,
    )
    return request, packet


def test_mock_output_validates_against_its_own_packet() -> None:
    request, packet = _request("Synthetic heading")
    draft = MockAnswerModel().answer(request)
    validated = validate_draft(draft, packet)  # type: ignore[arg-type]
    assert isinstance(validated, tuple)
    assert "Synthetic heading" in validated[0].statement


def test_mock_handles_a_packet_with_no_heading() -> None:
    request, packet = _request(None)
    draft = MockAnswerModel().answer(request)
    validated = validate_draft(draft, packet)  # type: ignore[arg-type]
    assert isinstance(validated, tuple)
    assert validated[0].citation.pinpoint == request.pinpoint


def test_mock_never_emits_a_quote() -> None:
    request, _ = _request("Synthetic heading")
    draft = MockAnswerModel().answer(request)
    assert all(p.citation.quote is None for p in draft.propositions)

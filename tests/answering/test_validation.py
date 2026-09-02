"""Deterministic citation validation, including adversarial model output."""

from __future__ import annotations

import pytest

from legal_ai.answering.models import DraftCitation, DraftProposition, ModelDraft, Proposition
from legal_ai.answering.types import AnswerRefusalCode
from legal_ai.answering.validation import validate_draft
from tests.answering.conftest import FOREIGN_SHA256, build_packet, draft_for


def test_valid_draft_is_accepted() -> None:
    packet = build_packet()
    validated = validate_draft(draft_for(packet), packet)
    assert isinstance(validated, tuple)
    assert len(validated) == 1
    assert validated[0].citation.sha256 == packet.sha256


def test_empty_draft_refuses() -> None:
    packet = build_packet()
    assert validate_draft(ModelDraft(propositions=()), packet) is (
        AnswerRefusalCode.NO_PROPOSITIONS
    )


def test_oversized_draft_refuses() -> None:
    packet = build_packet()
    single = draft_for(packet).propositions[0]
    draft = ModelDraft(propositions=tuple(single for _ in range(21)))
    assert validate_draft(draft, packet) is AnswerRefusalCode.MODEL_OUTPUT_MALFORMED


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"source_id": "wa_legislation:invented:1"}, AnswerRefusalCode.CITATION_SOURCE_UNKNOWN),
        ({"sha256": FOREIGN_SHA256}, AnswerRefusalCode.CITATION_DIGEST_MISMATCH),
        ({"provision_identifier": "s 99"}, AnswerRefusalCode.CITATION_PROVISION_MISMATCH),
        ({"pinpoint": "section 99"}, AnswerRefusalCode.CITATION_PINPOINT_MISMATCH),
        (
            {"quote": "a sentence never present in the source"},
            AnswerRefusalCode.QUOTE_NOT_IN_SOURCE,
        ),
    ],
)
def test_unsupported_citation_refuses_the_whole_answer(
    overrides: dict[str, str], expected: AnswerRefusalCode
) -> None:
    packet = build_packet()
    assert validate_draft(draft_for(packet, **overrides), packet) is expected


def test_quote_present_in_the_verified_bytes_is_kept() -> None:
    packet = build_packet()
    quote = "Driver in incident occasioning property damage"
    assert quote.encode("utf-8") in packet.source_content
    validated = validate_draft(draft_for(packet, quote=quote), packet)
    assert isinstance(validated, tuple)
    assert validated[0].citation.quote == quote


def test_one_bad_proposition_refuses_every_proposition() -> None:
    packet = build_packet()
    good = draft_for(packet).propositions[0]
    bad = DraftProposition(
        statement="An invented obligation.",
        citation=DraftCitation(
            source_id=packet.source_id,
            provision_identifier="s 404",
            pinpoint=packet.pinpoint,
            sha256=packet.sha256,
        ),
    )
    result = validate_draft(ModelDraft(propositions=(good, bad)), packet)
    assert result is AnswerRefusalCode.CITATION_PROVISION_MISMATCH


def test_citation_identity_is_taken_from_the_packet_not_the_model() -> None:
    """A model cannot restate the Act title, URL, or version; those come from the packet."""

    packet = build_packet()
    validated = validate_draft(draft_for(packet), packet)
    assert isinstance(validated, tuple)
    citation = validated[0].citation
    assert citation.act_title == packet.act.title
    assert citation.official_source_url == packet.official_source_url
    assert citation.source_version == packet.source_version


def test_validated_proposition_is_immutable() -> None:
    packet = build_packet()
    validated = validate_draft(draft_for(packet), packet)
    assert isinstance(validated, tuple)
    proposition: Proposition = validated[0]
    with pytest.raises(ValueError):
        proposition.statement = "rewritten"

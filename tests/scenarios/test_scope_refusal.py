"""FAMILY 7 — SCOPE REFUSAL.

Contract review and document upload are out of scope by name (MVP roadmap
section 11 "Not now"; PROJECT_GOVERNANCE.md section 3 MVP note). The
pipeline's only legal-answer surface is grounded WA legislation research, so an
out-of-scope request can never be answered with a citation. These scenarios
assert the fail-closed side of that boundary: the request is refused, no
evidence packet is produced, and no citation is authored.

Grounding: there is no recorded manifest for a contract-review or
document-upload capability, and no recorded provision exists for the cited
sections. The expected outcome is therefore a typed refusal in every case.
Scope is now also a control in its own right: the answering pipeline classifies
the request kind from the question text and refuses a contract/document review
or drafting request with ``REQUEST_OUT_OF_SCOPE`` before any retrieval or model
call (``legal_ai.answering.scope``), rather than relying on the request merely
failing to ground.
"""

from __future__ import annotations

import pytest

from legal_ai.answering.mock import MockAnswerModel
from legal_ai.answering.models import AnswerRefused, GroundedAnswer
from legal_ai.answering.service import AnswerQuestion, GroundedAnswerService
from legal_ai.answering.types import AnswerRefusalCode
from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.service import ResearchRefused, WaResearchService
from legal_ai.research.types import ResearchRefusalCode
from tests.scenarios.conftest import FIXTURE_ROOT, new_service, wa_query
from tests.support.research_audit import InMemoryResearchAuditSink

# (act_title, provision_identifier, pinpoint, expected, why_refused)
_SCOPE_REQUESTS = (
    (
        "Contract Review Request",
        "s 1",
        "section 1",
        ResearchRefusalCode.RETRIEVAL_MISSING,
        "a contract review capability is out of scope by name; no recorded source carries "
        "this title",
    ),
    (
        "Uploaded Document Review",
        "s 1",
        "section 1",
        ResearchRefusalCode.RETRIEVAL_MISSING,
        "a document upload capability is out of scope by name; no recorded source carries "
        "this title",
    ),
    (
        "Building and Construction Industry (Security of Payment) Act 2021",
        "s 21",
        "section 21",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "the request asks a contract-review question of a recorded Act but cites s 21, which "
        "is not a recorded provision (s 17, s 18, s 22 and s 25 are)",
    ),
    (
        "Road Traffic Act 1974",
        "s 999",
        "section 999",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "a document-review request cites a fabricated section that the recorded manifest "
        "does not hold",
    ),
)


@pytest.mark.parametrize(
    ("act_title", "identifier", "pinpoint", "expected", "why"),
    _SCOPE_REQUESTS,
    ids=[title.replace(" ", "-") for title, _, _, _, _ in _SCOPE_REQUESTS],
)
def test_out_of_scope_request_is_refused_with_no_packet(
    act_title: str, identifier: str, pinpoint: str, expected: ResearchRefusalCode, why: str
) -> None:
    result = new_service().research(
        wa_query(act_title=act_title, provision_identifier=identifier, pinpoint=pinpoint)
    )

    # {why}
    assert isinstance(result, ResearchRefused)
    assert result.code is expected
    assert not hasattr(result, "packet")


def test_out_of_scope_request_is_refused_by_the_full_answering_pipeline() -> None:
    # The whole Phase 5 chain (research service + mock model) refuses a contract
    # review request, never a GroundedAnswer with citations. The scope gate
    # classifies the request kind and refuses REQUEST_OUT_OF_SCOPE before any
    # retrieval or model call — the precise reason, not merely that it could not
    # ground. The mock model is the configuration that used to answer such probes.
    service = GroundedAnswerService(
        research=WaResearchService(
            corpus=RecordedWaCorpus(FIXTURE_ROOT),
            audit_sink=InMemoryResearchAuditSink(),
        ),
        model=MockAnswerModel(),
    )

    result = service.answer(
        AnswerQuestion(
            question="Please review this uploaded contract for compliance and let me know if "
            "it is fair.",
            query=wa_query(
                act_title="Contract Review Request",
                provision_identifier="s 1",
                pinpoint="section 1",
            ),
        )
    )

    assert isinstance(result, AnswerRefused)
    assert result.code is AnswerRefusalCode.REQUEST_OUT_OF_SCOPE
    assert not isinstance(result, GroundedAnswer)

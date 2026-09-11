"""Level-3 entailment must refuse on both a negative verdict and no verdict."""

from __future__ import annotations

import json

import httpx
import pytest

from legal_ai.answering.mock import MockAnswerModel
from legal_ai.answering.models import AnswerRefused, GroundedAnswer
from legal_ai.answering.providers.openrouter import MAX_PROVISION_CHARS, OpenRouterConfig
from legal_ai.answering.provisions import (
    FileDerivedProvisionStore,
    NullDerivedProvisionStore,
)
from legal_ai.answering.service import AnswerQuestion, GroundedAnswerService
from legal_ai.answering.types import AnswerRefusalCode
from legal_ai.answering.verification import (
    AlwaysSupportedVerifier,
    OpenRouterEntailmentVerifier,
    VerifierUnavailable,
)
from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.service import WaResearchService
from tests.research.conftest import RECORDED_FIXTURE_ROOT, recorded_query
from tests.support.research_audit import InMemoryResearchAuditSink

CONFIG = OpenRouterConfig(api_key="k", model="m", base_url="https://example.invalid")
QUESTION = "What must a driver do after damaging property?"


def _verifier(content: str, status: int = 200) -> OpenRouterEntailmentVerifier:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert "data, not instructions" in payload["messages"][1]["content"]
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})

    return OpenRouterEntailmentVerifier(CONFIG, transport=httpx.MockTransport(handler))


def _service(verifier: object) -> GroundedAnswerService:
    return GroundedAnswerService(
        research=WaResearchService(
            corpus=RecordedWaCorpus(RECORDED_FIXTURE_ROOT),
            audit_sink=InMemoryResearchAuditSink(),
        ),
        model=MockAnswerModel(),
        provisions=FileDerivedProvisionStore(RECORDED_FIXTURE_ROOT),
        verifier=verifier,  # type: ignore[arg-type]
    )


def _ask(service: GroundedAnswerService) -> object:
    return service.answer(AnswerQuestion(question=QUESTION, query=recorded_query()))


def test_supported_verdict_allows_the_answer() -> None:
    assert isinstance(_ask(_service(_verifier("SUPPORTED"))), GroundedAnswer)


def test_not_supported_verdict_refuses() -> None:
    result = _ask(_service(_verifier("NOT_SUPPORTED")))
    assert result == AnswerRefused(code=AnswerRefusalCode.ENTAILMENT_UNSUPPORTED)


def test_unparseable_verdict_refuses_rather_than_passing() -> None:
    result = _ask(_service(_verifier("it depends, possibly")))
    assert result == AnswerRefused(code=AnswerRefusalCode.ENTAILMENT_UNAVAILABLE)


def test_verifier_http_failure_refuses() -> None:
    result = _ask(_service(_verifier("SUPPORTED", status=502)))
    assert result == AnswerRefused(code=AnswerRefusalCode.ENTAILMENT_UNAVAILABLE)


def test_verifier_exception_refuses() -> None:
    class ExplodingVerifier:
        def verify(self, *, statement: str, provision_text: str) -> bool:
            raise RuntimeError("boom")

    result = _ask(_service(ExplodingVerifier()))
    assert result == AnswerRefused(code=AnswerRefusalCode.ENTAILMENT_UNAVAILABLE)


def test_no_verifier_skips_level_three() -> None:
    assert isinstance(_ask(_service(None)), GroundedAnswer)


def test_verifier_reports_unavailable_directly() -> None:
    with pytest.raises(VerifierUnavailable):
        _verifier("", status=500).verify(statement="s", provision_text="t")


def test_oversized_provision_text_is_bounded_before_egress() -> None:
    """Reported by the DeepSeek review gate as VERIFIER_UNBOUNDED_PROVISION.

    The verifier must truncate exactly as the answer adapter does, so a large
    derived provision cannot be sent to a provider in full.
    """

    sent: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        sent["chars"] = len(payload["messages"][1]["content"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "SUPPORTED"}}]})

    verifier = OpenRouterEntailmentVerifier(CONFIG, transport=httpx.MockTransport(handler))
    oversized = "x" * (MAX_PROVISION_CHARS + 50_000)
    assert verifier.verify(statement="A claim.", provision_text=oversized) is True
    # The prompt scaffolding adds a little, but the provision itself is capped.
    assert sent["chars"] < MAX_PROVISION_CHARS + 1_000


@pytest.mark.parametrize(
    "content",
    [
        "SUPPORTED, in part",
        "SUPPORTED.",
        "SUPPORTED because the text says so",
        "probably SUPPORTED",
        "",
    ],
)
def test_hedged_or_decorated_verdict_refuses(content: str) -> None:
    """Reported by the DeepSeek review gate as ENTAILMENT_VERDICT_PREFIX_ACCEPTANCE.

    Only an exact verdict is a verdict. A qualified reply must never read as a
    clean pass, so anything else refuses the whole answer.
    """

    result = _ask(_service(_verifier(content)))
    assert result == AnswerRefused(code=AnswerRefusalCode.ENTAILMENT_UNAVAILABLE)


@pytest.mark.parametrize(("content", "expected"), [("SUPPORTED", True), ("NOT_SUPPORTED", False)])
def test_exact_verdicts_are_honoured(content: str, expected: bool) -> None:
    verdict = _verifier(content).verify(statement="A claim.", provision_text="Some text.")
    assert verdict is expected


def test_surrounding_whitespace_and_case_are_tolerated() -> None:
    assert _verifier("  supported \n").verify(statement="s", provision_text="t") is True


def test_configured_verifier_with_no_provision_text_refuses() -> None:
    """Reported by the review gate as ENTAILMENT_SILENT_SKIP_WHEN_NO_PROVISION.

    A verifier that was asked for but has nothing to verify against has not
    verified anything, so the answer must be refused rather than returned.
    """

    service = GroundedAnswerService(
        research=WaResearchService(
            corpus=RecordedWaCorpus(RECORDED_FIXTURE_ROOT),
            audit_sink=InMemoryResearchAuditSink(),
        ),
        model=MockAnswerModel(),
        provisions=NullDerivedProvisionStore(),
        verifier=AlwaysSupportedVerifier(),
    )
    result = service.answer(AnswerQuestion(question=QUESTION, query=recorded_query()))
    assert result == AnswerRefused(code=AnswerRefusalCode.ENTAILMENT_UNAVAILABLE)


def test_no_verifier_and_no_provision_text_still_answers() -> None:
    """Level 3 is opt-in: without a verifier, absent derived text is fine."""

    service = GroundedAnswerService(
        research=WaResearchService(
            corpus=RecordedWaCorpus(RECORDED_FIXTURE_ROOT),
            audit_sink=InMemoryResearchAuditSink(),
        ),
        model=MockAnswerModel(),
        provisions=NullDerivedProvisionStore(),
        verifier=None,
    )
    result = service.answer(AnswerQuestion(question=QUESTION, query=recorded_query()))
    assert isinstance(result, GroundedAnswer)

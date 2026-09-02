"""Level-3 entailment must refuse on both a negative verdict and no verdict."""

from __future__ import annotations

import json

import httpx
import pytest

from legal_ai.answering.mock import MockAnswerModel
from legal_ai.answering.models import AnswerRefused, GroundedAnswer
from legal_ai.answering.providers.openrouter import OpenRouterConfig
from legal_ai.answering.provisions import FileDerivedProvisionStore
from legal_ai.answering.service import AnswerQuestion, GroundedAnswerService
from legal_ai.answering.types import AnswerRefusalCode
from legal_ai.answering.verification import (
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

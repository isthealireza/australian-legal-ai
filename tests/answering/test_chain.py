"""Provider fallback: resilient in who is asked, unchanged in what is believed."""

from __future__ import annotations

import time

import pytest

from legal_ai.answering.errors import AnswerModelUnavailable
from legal_ai.answering.models import GroundedAnswerRequest, ModelDraft
from legal_ai.answering.providers.chain import ChainedAnswerModel, NamedAnswerModel
from legal_ai.answering.verification import (
    ChainedEntailmentVerifier,
    NamedVerifier,
    VerifierUnavailable,
)
from tests.answering.conftest import build_recorded_packet, draft_for


def _request() -> GroundedAnswerRequest:
    packet = build_recorded_packet()
    return GroundedAnswerRequest(
        question="What must a driver do?",
        source_id=packet.source_id,
        act_title=packet.act.title,
        provision_identifier=packet.provision_identifier,
        pinpoint=packet.pinpoint,
        provision_heading=packet.provision_heading,
        source_version=packet.source_version,
        compilation_date=packet.compilation_date,
        official_source_url=packet.official_source_url,
        sha256=packet.sha256,
        source_content=packet.source_content,
        provision_text="the driver must stop immediately",
        provision_sha256=packet.sha256,
    )


class _Working:
    def __init__(self) -> None:
        self.calls = 0

    def answer(self, request: GroundedAnswerRequest) -> ModelDraft:
        self.calls += 1
        return draft_for(build_recorded_packet())


class _Failing:
    def __init__(self, message: str = "provider down") -> None:
        self.calls = 0
        self._message = message

    def answer(self, request: GroundedAnswerRequest) -> ModelDraft:
        self.calls += 1
        raise AnswerModelUnavailable(self._message)


class _Slow:
    """Consumes its whole allowance, then fails, as a stalled provider would."""

    def __init__(self) -> None:
        self.granted: list[float] = []

    def answer(self, request: GroundedAnswerRequest) -> ModelDraft:
        return self.answer_within(request, deadline_seconds=1.0)

    def answer_within(
        self, request: GroundedAnswerRequest, *, deadline_seconds: float
    ) -> ModelDraft:
        self.granted.append(deadline_seconds)
        time.sleep(min(deadline_seconds, 0.2))
        raise AnswerModelUnavailable("stalled")


def test_the_primary_is_used_when_it_works() -> None:
    primary, fallback = _Working(), _Working()
    chain = ChainedAnswerModel(
        [NamedAnswerModel("primary", primary), NamedAnswerModel("fallback", fallback)]
    )
    outcome = chain.answer_with_provider(_request())
    assert outcome.provider == "primary"
    assert fallback.calls == 0, "a working primary must not consult the fallback"


def test_a_failing_primary_falls_through_to_the_fallback() -> None:
    primary, fallback = _Failing(), _Working()
    chain = ChainedAnswerModel(
        [NamedAnswerModel("primary", primary), NamedAnswerModel("fallback", fallback)]
    )
    outcome = chain.answer_with_provider(_request())
    assert outcome.provider == "fallback"
    assert primary.calls == 1 and fallback.calls == 1


def test_the_chain_walks_all_the_way_to_the_final_fallback() -> None:
    final = _Working()
    chain = ChainedAnswerModel(
        [
            NamedAnswerModel("primary", _Failing()),
            NamedAnswerModel("fallback", _Failing()),
            NamedAnswerModel("final", final),
        ]
    )
    assert chain.answer_with_provider(_request()).provider == "final"


def test_every_provider_failing_raises_the_typed_fault() -> None:
    """This is what becomes MODEL_UNAVAILABLE, the existing typed refusal."""

    chain = ChainedAnswerModel(
        [NamedAnswerModel("a", _Failing()), NamedAnswerModel("b", _Failing())]
    )
    with pytest.raises(AnswerModelUnavailable, match="every answer provider failed"):
        chain.answer_with_provider(_request())


def test_a_credential_never_appears_in_the_chain_error() -> None:
    chain = ChainedAnswerModel([NamedAnswerModel("a", _Failing("boom"))])
    with pytest.raises(AnswerModelUnavailable) as caught:
        chain.answer_with_provider(_request())
    assert "sk-" not in str(caught.value)


def test_attempts_share_one_budget_so_fallbacks_cannot_extend_the_deadline() -> None:
    """Adding providers must not push the total past the interface's abort."""

    slow_a, slow_b = _Slow(), _Slow()
    chain = ChainedAnswerModel(
        [NamedAnswerModel("a", slow_a), NamedAnswerModel("b", slow_b)],
        phase_seconds=0.3,
        attempt_seconds=0.2,
    )
    started = time.monotonic()
    with pytest.raises(AnswerModelUnavailable):
        chain.answer_with_provider(_request())
    elapsed = time.monotonic() - started

    assert elapsed < 1.5, f"the shared budget was not honoured: {elapsed:.2f}s"
    assert all(granted <= 0.2 for granted in slow_a.granted + slow_b.granted)


def test_an_exhausted_budget_stops_before_trying_another_provider() -> None:
    never = _Working()
    chain = ChainedAnswerModel(
        [NamedAnswerModel("slow", _Slow()), NamedAnswerModel("never", never)],
        phase_seconds=0.15,
        attempt_seconds=0.15,
    )
    with pytest.raises(AnswerModelUnavailable):
        chain.answer_with_provider(_request())
    assert never.calls == 0, "the budget was already spent; no further provider may be tried"


class _Verifier:
    def __init__(self, verdict: bool = True, fails: bool = False) -> None:
        self.calls = 0
        self._verdict = verdict
        self._fails = fails

    def verify(self, *, statement: str, provision_text: str) -> bool:
        self.calls += 1
        if self._fails:
            raise VerifierUnavailable("verifier down")
        return self._verdict


def test_verification_skips_the_provider_that_wrote_the_statement() -> None:
    """A model must never be the proof of its own output."""

    same, other = _Verifier(), _Verifier()
    chain = ChainedEntailmentVerifier(
        [NamedVerifier("openrouter", same), NamedVerifier("deepseek", other)]
    )
    assert chain.verify_excluding(statement="s", provision_text="t", exclude="openrouter") is True
    assert same.calls == 0, "the answering provider must not verify itself"
    assert other.calls == 1


def test_verification_refuses_when_exclusion_leaves_nobody() -> None:
    only = _Verifier()
    chain = ChainedEntailmentVerifier([NamedVerifier("openrouter", only)])
    with pytest.raises(VerifierUnavailable, match="cannot verify its own output"):
        chain.verify_excluding(statement="s", provision_text="t", exclude="openrouter")
    assert only.calls == 0


def test_verification_falls_through_an_unavailable_provider() -> None:
    down, up = _Verifier(fails=True), _Verifier()
    chain = ChainedEntailmentVerifier([NamedVerifier("a", down), NamedVerifier("b", up)])
    assert chain.verify_excluding(statement="s", provision_text="t", exclude=None) is True
    assert down.calls == 1 and up.calls == 1


def test_a_negative_verdict_is_returned_not_retried_elsewhere() -> None:
    """NOT_SUPPORTED is an answer, not a failure. Retrying would shop for a pass."""

    refuses, permissive = _Verifier(verdict=False), _Verifier(verdict=True)
    chain = ChainedEntailmentVerifier([NamedVerifier("a", refuses), NamedVerifier("b", permissive)])
    assert chain.verify_excluding(statement="s", provision_text="t", exclude=None) is False
    assert permissive.calls == 0, "a refusal must not be re-run against a softer verifier"

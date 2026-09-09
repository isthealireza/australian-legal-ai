"""Per-proposition entailment: verify and report each proposition on its own.

Before this change the pipeline was all-or-nothing: one proposition failing
level 3 refused the whole answer. The more subsections a provision has, the more
propositions an answer carries, and the more likely one fails — so the richest
provisions (Owner-Drivers s 7, Sale of Goods s 14, each answered with four
propositions live) refused end to end (see LIVE_ADVERSARIAL_RUN_2.md family C
and the residual finding in the fix scope card).

The unit of the entailment decision is now one proposition, not the whole
answer. Supported propositions are returned with their citations; an unsupported
or unverifiable one is dropped and named with its reason; the answer records
that a part was withheld. A wholly unsupported answer still refuses entirely.
The per-proposition check is exactly as strict as before — only the unit changed.
"""

from __future__ import annotations

import pytest

from legal_ai.answering.models import (
    AnswerRefused,
    DraftCitation,
    DraftProposition,
    GroundedAnswer,
    GroundedAnswerRequest,
    ModelDraft,
    WithheldReason,
)
from legal_ai.answering.provisions import FileDerivedProvisionStore
from legal_ai.answering.service import AnswerQuestion, GroundedAnswerService
from legal_ai.answering.types import AnswerRefusalCode
from legal_ai.answering.verification import VerifierUnavailable
from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.service import WaResearchService
from tests.research.conftest import RECORDED_FIXTURE_ROOT, recorded_query
from tests.support.research_audit import InMemoryResearchAuditSink

# Real recorded cases. Each quote below is an exact substring of the recorded
# provision text; each statement is the claim graded by the verifier.
ODA_S7 = {
    "act_title": "Owner-Drivers (Contracts and Disputes) Act 2007",
    "provision_identifier": "s 7",
    "pinpoint": "section 7",
}
SGA_S14 = {
    "act_title": "Sale of Goods Act 1895",
    "provision_identifier": "s 14",
    "pinpoint": "section 14",
}

# (statement, exact-substring quote). The third s 7 proposition is the real
# residual misstatement: the statute says "whether in an owner-driver contract
# AND whether in writing or not"; the answer rephrased it as "OR not".
S7_PROPS = [
    (
        "A provision purporting to exclude, modify or restrict the operation of the Act "
        "or the code of conduct has no effect.",
        "purports to exclude, modify or restrict the operation of this Act or the code of conduct",
    ),
    (
        "The invalidity of one provision does not affect the other provisions of the agreement.",
        "does not prejudice or affect the operation of other provisions of the agreement or "
        "arrangement",
    ),
    (
        "Any purported waiver of an entitlement under the Act, whether in an owner-driver "
        "contract or not, has no effect.",
        "Any purported waiver, whether in an owner-driver contract and whether in writing or "
        "not, of an entitlement under this Act has no effect.",
    ),
    (
        "For the first six months after the section operates, a contrary provision of an "
        "owner-driver contract prevails to the extent of the inconsistency.",
        "prevails to the extent of the inconsistency",
    ),
]
S7_BAD_STATEMENT = S7_PROPS[2][0]

S14_PROPS = [
    (
        "There is an implied condition that goods are reasonably fit for a particular purpose "
        "where the buyer makes that purpose known and relies on the seller's skill.",
        "there is an implied condition that the goods shall be reasonably fit for such purpose",
    ),
    (
        "There is an implied condition that goods bought by description are of merchantable "
        "quality.",
        "there is an implied condition that the goods shall be of merchantable quality",
    ),
    (
        "Section 14 guarantees that every good sold is fit for every possible purpose.",
        "there is an implied condition that the goods shall be reasonably fit for such purpose",
    ),
    (
        "An implied warranty or condition as to quality or fitness may be annexed by trade usage.",
        "An implied warranty or condition as to quality or fitness for a particular purpose may "
        "be annexed by the usage of trade",
    ),
]
S14_BAD_STATEMENT = S14_PROPS[2][0]


class ScriptedAnswerModel:
    """An answer-model double that emits fixed propositions, citing the packet.

    Citation identity is taken from the request exactly as the real adapter does,
    so the draft passes levels 1 and 2 and only entailment is exercised.
    """

    name = "scripted"

    def __init__(self, props: list[tuple[str, str]]) -> None:
        self._props = props

    def answer(self, request: GroundedAnswerRequest) -> ModelDraft:
        return ModelDraft(
            propositions=tuple(
                DraftProposition(
                    statement=statement,
                    citation=DraftCitation(
                        source_id=request.source_id,
                        provision_identifier=request.provision_identifier,
                        pinpoint=request.pinpoint,
                        sha256=request.sha256,
                        quote=quote,
                    ),
                )
                for statement, quote in self._props
            )
        )


class ReplayVerifier:
    """Grades each statement from a recorded map. None replays an outage."""

    def __init__(self, verdicts: dict[str, bool | None]) -> None:
        self._verdicts = verdicts

    def verify(self, *, statement: str, provision_text: str) -> bool:
        del provision_text
        verdict = self._verdicts[statement]
        if verdict is None:
            raise VerifierUnavailable("recorded unavailable")
        return verdict


def _service_with(model: object, verifier: object) -> GroundedAnswerService:
    return GroundedAnswerService(
        research=WaResearchService(
            corpus=RecordedWaCorpus(RECORDED_FIXTURE_ROOT),
            audit_sink=InMemoryResearchAuditSink(),
        ),
        model=model,  # type: ignore[arg-type]
        provisions=FileDerivedProvisionStore(RECORDED_FIXTURE_ROOT),
        verifier=verifier,  # type: ignore[arg-type]
    )


def _service(
    props: list[tuple[str, str]], verdicts: dict[str, bool | None]
) -> GroundedAnswerService:
    return _service_with(ScriptedAnswerModel(props), ReplayVerifier(verdicts))


def _ask(service: GroundedAnswerService, query_fields: dict[str, str]) -> object:
    return service.answer(
        AnswerQuestion(question="What does the provision do?", query=recorded_query(**query_fields))
    )


def _verdicts(
    props: list[tuple[str, str]], failing: str, *, unavailable: bool = False
) -> dict[str, bool | None]:
    out: dict[str, bool | None] = {}
    for statement, _ in props:
        if statement == failing:
            out[statement] = None if unavailable else False
        else:
            out[statement] = True
    return out


@pytest.mark.parametrize(
    ("props", "query", "failing"),
    [
        (S7_PROPS, ODA_S7, S7_BAD_STATEMENT),
        (S14_PROPS, SGA_S14, S14_BAD_STATEMENT),
    ],
    ids=["owner_drivers_s7", "sale_of_goods_s14"],
)
def test_one_unsupported_proposition_is_dropped_not_the_whole_answer(
    props: list[tuple[str, str]], query: dict[str, str], failing: str
) -> None:
    result = _ask(_service(props, _verdicts(props, failing)), query)

    assert isinstance(result, GroundedAnswer)
    # The three supported propositions are returned, the failing one is not.
    returned = {p.statement for p in result.propositions}
    assert len(result.propositions) == 3
    assert failing not in returned
    # The withheld one is named by its pinpoint and its reason.
    assert len(result.withheld) == 1
    assert result.withheld[0].reason is WithheldReason.UNSUPPORTED
    assert result.withheld[0].pinpoint == query["pinpoint"]


def test_an_unverifiable_proposition_is_withheld_but_the_rest_still_answer() -> None:
    result = _ask(
        _service(S7_PROPS, _verdicts(S7_PROPS, S7_BAD_STATEMENT, unavailable=True)), ODA_S7
    )

    assert isinstance(result, GroundedAnswer)
    assert len(result.propositions) == 3
    assert S7_BAD_STATEMENT not in {p.statement for p in result.propositions}
    assert len(result.withheld) == 1
    # A verifier outage on one proposition withholds only that proposition, and
    # is named distinctly from an unsupported verdict.
    assert result.withheld[0].reason is WithheldReason.UNVERIFIED


class _RaisingVerifier:
    """Raises a non-`VerifierUnavailable` error for one statement, True otherwise.

    Confirms the broad fault path: any verifier exception withholds only the one
    proposition it graded and never reads as a pass.
    """

    def __init__(self, failing: str) -> None:
        self._failing = failing

    def verify(self, *, statement: str, provision_text: str) -> bool:
        del provision_text
        if statement == self._failing:
            raise RuntimeError("boom")
        return True


def test_a_generic_verifier_fault_withholds_only_that_proposition() -> None:
    service = _service_with(ScriptedAnswerModel(S7_PROPS), _RaisingVerifier(S7_BAD_STATEMENT))
    result = _ask(service, ODA_S7)
    assert isinstance(result, GroundedAnswer)
    assert len(result.propositions) == 3
    assert S7_BAD_STATEMENT not in {p.statement for p in result.propositions}
    assert len(result.withheld) == 1
    assert result.withheld[0].reason is WithheldReason.UNVERIFIED


def test_a_wholly_unsupported_answer_still_refuses_entirely() -> None:
    verdicts: dict[str, bool | None] = {statement: False for statement, _ in S7_PROPS}
    result = _ask(_service(S7_PROPS, verdicts), ODA_S7)
    assert result == AnswerRefused(code=AnswerRefusalCode.ENTAILMENT_UNSUPPORTED)


def test_a_wholly_unverifiable_answer_refuses_as_unavailable() -> None:
    verdicts: dict[str, bool | None] = {statement: None for statement, _ in S7_PROPS}
    result = _ask(_service(S7_PROPS, verdicts), ODA_S7)
    assert result == AnswerRefused(code=AnswerRefusalCode.ENTAILMENT_UNAVAILABLE)


def test_all_supported_returns_every_proposition_and_no_withheld() -> None:
    verdicts: dict[str, bool | None] = {statement: True for statement, _ in S7_PROPS}
    result = _ask(_service(S7_PROPS, verdicts), ODA_S7)
    assert isinstance(result, GroundedAnswer)
    assert len(result.propositions) == 4
    assert result.withheld == ()


def test_api_render_surfaces_withheld_reason_without_leaking_the_statement() -> None:
    """The response must say a part was withheld and why, but must not republish

    the unverified statement text — a statement that failed entailment is exactly
    the confident-but-wrong content the pipeline exists to keep out of an answer.
    """

    from datetime import date

    from legal_ai.answering.models import (
        Citation,
        Proposition,
        WithheldProposition,
    )
    from legal_ai.api.schemas import render_answer

    citation = Citation(
        source_id="wa_legislation:owner_drivers_contracts_and_disputes_act_2007:consolidated:01-g0-00",
        act_title="Owner-Drivers (Contracts and Disputes) Act 2007",
        provision_identifier="s 7",
        pinpoint="section 7",
        source_version="01-g0-00",
        compilation_date=date(2025, 1, 31),
        official_source_url="https://www.legislation.wa.gov.au/x.html",
        sha256="03071c9fe15dfdc3a8c26ebfd9027f5ff6044f91c83e0455ace5b5ac40b43bad",
        quote="has no effect",
    )
    answer = GroundedAnswer(
        propositions=(Proposition(statement="A supported claim.", citation=citation),),
        withheld=(
            WithheldProposition(
                statement=S7_BAD_STATEMENT,
                pinpoint="section 7",
                reason=WithheldReason.UNSUPPORTED,
            ),
        ),
    )

    body = render_answer(answer, "disclaimer")
    dumped = body.model_dump_json()

    assert body.outcome == "ANSWERED"
    assert len(body.withheld) == 1
    assert body.withheld[0].pinpoint == "section 7"
    assert body.withheld[0].reason == "UNSUPPORTED"
    # A plain, human-visible signal that the answer is partial.
    assert body.partial is True
    # The unverified statement text is never republished, anywhere in the body.
    assert S7_BAD_STATEMENT not in dumped

    # A complete answer renders as not partial with no withheld entries.
    supported = Proposition(statement="A supported claim.", citation=citation)
    complete = render_answer(GroundedAnswer(propositions=(supported,)), "disclaimer")
    assert complete.partial is False
    assert complete.withheld == ()

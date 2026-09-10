"""Provision routing: the user describes a problem, the system picks the provision.

Routing adds a step in front of the existing pipeline and weakens nothing behind
it. It selects only from the recorded catalogue, validates the model's choice
deterministically against that catalogue before anything else runs, and yields
one of: a chosen provision (which then runs the unchanged answer pipeline), a
short candidate list for the user to confirm, or a refusal — never a nearest
match, never an invented Act or section. An out-of-scope request is refused by
the existing scope gate before the router spends a model call.
"""

from __future__ import annotations

import pytest

from legal_ai.answering.mock import MockAnswerModel
from legal_ai.answering.models import GroundedAnswer
from legal_ai.answering.provisions import FileDerivedProvisionStore
from legal_ai.answering.routing import (
    ProvisionRoutingService,
    RouteCandidates,
    RoutedAnswer,
    RouterChoiceDraft,
    RouterDraft,
    RouteRefusalCode,
    RouteRefused,
    RouterUnavailable,
    validate_route,
)
from legal_ai.answering.service import AnswerQuestion, GroundedAnswerService
from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.models import ResearchQuery
from legal_ai.research.service import WaResearchService
from tests.research.conftest import RECORDED_FIXTURE_ROOT
from tests.support.research_audit import InMemoryResearchAuditSink

_CATALOGUE = FileDerivedProvisionStore(RECORDED_FIXTURE_ROOT).catalogue()


class ScriptedRouter:
    """A router double that returns a fixed draft, ignoring the problem text."""

    def __init__(self, *choices: tuple[str, str, str]) -> None:
        self._draft = RouterDraft(
            choices=tuple(
                RouterChoiceDraft(act_title=a, provision_identifier=p, reason=r)
                for a, p, r in choices
            )
        )

    def route(self, *, problem: str, catalogue: object) -> RouterDraft:
        del problem, catalogue
        return self._draft


class ExplodingRouter:
    """Fails if the router is reached. Proves a pre-router refusal."""

    def route(self, *, problem: str, catalogue: object) -> RouterDraft:
        del problem, catalogue
        raise AssertionError("the router must not be called for an out-of-scope request")


class UnavailableRouter:
    """Simulates a router outage."""

    def route(self, *, problem: str, catalogue: object) -> RouterDraft:
        del problem, catalogue
        raise RouterUnavailable("router is down")


def _answer_service() -> GroundedAnswerService:
    return GroundedAnswerService(
        research=WaResearchService(
            corpus=RecordedWaCorpus(RECORDED_FIXTURE_ROOT),
            audit_sink=InMemoryResearchAuditSink(),
        ),
        model=MockAnswerModel(),
        provisions=FileDerivedProvisionStore(RECORDED_FIXTURE_ROOT),
        verifier=None,
    )


def _service(router: object) -> ProvisionRoutingService:
    return ProvisionRoutingService(
        router=router,  # type: ignore[arg-type]
        answer_service=_answer_service(),
        catalogue=_CATALOGUE,
    )


# --- routing behaviour ---


def test_a_clear_problem_routes_to_the_right_provision() -> None:
    router = ScriptedRouter(
        ("Road Traffic Act 1974", "s 55", "Failing to stop after property damage."),
    )
    result = _service(router).route(
        "I reversed into a parked car and drove off. What was I supposed to do?"
    )
    assert isinstance(result, RoutedAnswer)
    assert result.choice.act_title == "Road Traffic Act 1974"
    assert result.choice.provision_identifier == "s 55"
    assert result.choice.pinpoint == "section 55"
    # The routed provision runs the unchanged pipeline; the mock answers it.
    assert isinstance(result.answer, GroundedAnswer)


def test_a_problem_spanning_two_acts_returns_candidates_not_one_guess() -> None:
    router = ScriptedRouter(
        ("Sale of Goods Act 1895", "s 14", "Implied quality of goods."),
        ("Fair Trading Act 2010", "s 18", "Australian Consumer Law."),
    )
    result = _service(router).route("The goods I bought are faulty and the seller misled me.")
    assert isinstance(result, RouteCandidates)
    assert len(result.choices) == 2
    idents = {(c.act_title, c.provision_identifier) for c in result.choices}
    assert ("Sale of Goods Act 1895", "s 14") in idents
    assert ("Fair Trading Act 2010", "s 18") in idents


# Near-miss cases from LIVE_ADVERSARIAL_RUN_2.md family E/N: a section that
# exists in one recorded Act, named against a different recorded Act, must never
# be silently accepted.
@pytest.mark.parametrize(
    "choices",
    [
        [("Sale of Goods Act 1895", "s 55", "near miss: s55 is Road Traffic, not SGA")],
        [("Motor Vehicle Dealers Act 1973", "s 18", "near miss: s18 is Fair Trading")],
        [("Owner-Drivers (Contracts and Disputes) Act 2007", "s 15", "near miss: s15 is MVD")],
        [("Residential Tenancies Act 1987", "s 1", "not in corpus at all")],
        [],
    ],
    ids=["s55_wrong_act", "s18_wrong_act", "s15_wrong_act", "act_not_in_corpus", "empty"],
)
def test_no_recorded_provision_returns_refusal_never_a_nearest_match(
    choices: list[tuple[str, str, str]],
) -> None:
    result = _service(ScriptedRouter(*choices)).route("Some problem the corpus does not cover.")
    assert result == RouteRefused(code=RouteRefusalCode.NO_MATCHING_PROVISION)


def test_a_routed_answer_matches_a_hand_picked_answer() -> None:
    # Route to s 55.
    routed = _service(
        ScriptedRouter(("Road Traffic Act 1974", "s 55", "duty after property damage"))
    ).route("What must I do after an incident causing property damage?")
    assert isinstance(routed, RoutedAnswer)
    assert isinstance(routed.answer, GroundedAnswer)

    # Hand-pick the identical provision and ask directly.
    hand = _answer_service().answer(
        AnswerQuestion(
            question="What must I do after an incident causing property damage?",
            query=ResearchQuery(
                jurisdiction="WA",
                act_title="Road Traffic Act 1974",
                provision_identifier="s 55",
                pinpoint="section 55",
            ),
        )
    )
    assert isinstance(hand, GroundedAnswer)
    # Same citations, same checks: routing only fills the query.
    routed_cites = [(p.citation.source_id, p.citation.sha256) for p in routed.answer.propositions]
    hand_cites = [(p.citation.source_id, p.citation.sha256) for p in hand.propositions]
    assert routed_cites == hand_cites


def test_out_of_scope_is_refused_before_the_router_is_called() -> None:
    result = _service(ExplodingRouter()).route(
        "Review this contract clause for me and tell me if I should sign it."
    )
    assert result == RouteRefused(code=RouteRefusalCode.REQUEST_OUT_OF_SCOPE)


def test_router_outage_is_a_refusal_not_a_guess() -> None:
    result = _service(UnavailableRouter()).route("A genuine research problem about driving.")
    assert result == RouteRefused(code=RouteRefusalCode.ROUTER_UNAVAILABLE)


# --- deterministic validation (the safety core) ---


def test_validate_route_maps_a_single_valid_choice_to_the_catalogue_canonical() -> None:
    draft = RouterDraft(
        choices=(
            RouterChoiceDraft(
                act_title="road traffic act 1974", provision_identifier="section 55", reason="x"
            ),
        )
    )
    from legal_ai.answering.routing import RoutedProvision

    decision = validate_route(draft, _CATALOGUE)
    assert isinstance(decision, RoutedProvision)
    # Canonical identity comes from the catalogue, not the model's phrasing.
    assert decision.choice.act_title == "Road Traffic Act 1974"
    assert decision.choice.provision_identifier == "s 55"
    assert decision.choice.pinpoint == "section 55"


def test_validate_route_drops_invalid_choices_and_keeps_valid_ones() -> None:
    draft = RouterDraft(
        choices=(
            RouterChoiceDraft(
                act_title="Sale of Goods Act 1895", provision_identifier="s 99", reason="invalid"
            ),
            RouterChoiceDraft(
                act_title="Sale of Goods Act 1895", provision_identifier="s 14", reason="valid"
            ),
        )
    )
    from legal_ai.answering.routing import RoutedProvision

    decision = validate_route(draft, _CATALOGUE)
    assert isinstance(decision, RoutedProvision)
    assert decision.choice.provision_identifier == "s 14"


def test_validate_route_caps_candidates_and_dedupes() -> None:
    draft = RouterDraft(
        choices=(
            RouterChoiceDraft(
                act_title="Sale of Goods Act 1895", provision_identifier="s 13", reason="a"
            ),
            RouterChoiceDraft(
                act_title="Sale of Goods Act 1895", provision_identifier="s 13", reason="dup"
            ),
            RouterChoiceDraft(
                act_title="Sale of Goods Act 1895", provision_identifier="s 14", reason="b"
            ),
            RouterChoiceDraft(
                act_title="Sale of Goods Act 1895", provision_identifier="s 15", reason="c"
            ),
            RouterChoiceDraft(
                act_title="Sale of Goods Act 1895", provision_identifier="s 16", reason="d"
            ),
        )
    )
    decision = validate_route(draft, _CATALOGUE)
    assert isinstance(decision, RouteCandidates)
    assert len(decision.choices) == 3  # deduped s13, then s14, s15 — capped at three
    assert [c.provision_identifier for c in decision.choices] == ["s 13", "s 14", "s 15"]

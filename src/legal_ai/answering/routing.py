"""Provision routing — choose the provision from a described problem.

The user describes a problem in free text; the router selects the provision to
research. Choosing among known options is judgement, not law, so the router may
use a model — but it chooses **only** from the catalogue the corpus returns, and
its choice is validated deterministically against that catalogue before anything
else runs. Routing adds a step in front of the existing pipeline (grounding,
citation validation, entailment, scope) and weakens nothing behind it.

Its outcome is exactly one of:

- a chosen provision, which then runs the unchanged answer pipeline;
- a short list of candidates for the user to confirm — ambiguity is not failure;
- a refusal, when nothing in the catalogue covers the problem — never a nearest
  match, never an invented Act or section.

An out-of-scope request (contract/document review or drafting) is refused by the
existing scope gate *before* the router spends a model call.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from ..research.corpus import normalize_for_match
from ..research.models import ResearchQuery
from ..research.types import WA_JURISDICTION
from .models import AnswerResult
from .provisions import CataloguedProvision
from .scope import RequestKind, classify_request_kind
from .service import AnswerQuestion, GroundedAnswerService

_LOGGER = logging.getLogger("legal_ai.answering.routing")

#: Ambiguity is fine, but a list longer than this is noise, not a choice.
MAX_ROUTE_CANDIDATES = 3


class RouteRefusalCode(StrEnum):
    """Why routing produced no provision to research."""

    #: The catalogue holds nothing that covers the described problem.
    NO_MATCHING_PROVISION = "NO_MATCHING_PROVISION"
    #: The request is outside the research boundary (handled before the router).
    REQUEST_OUT_OF_SCOPE = "REQUEST_OUT_OF_SCOPE"
    #: The router could not produce a decision (outage or fault). Fail-closed.
    ROUTER_UNAVAILABLE = "ROUTER_UNAVAILABLE"
    #: No provisions are indexed, so there is nothing to route to.
    CATALOGUE_EMPTY = "CATALOGUE_EMPTY"


@dataclass(frozen=True, slots=True)
class RouterChoiceDraft:
    """One untrusted choice asserted by the router model."""

    act_title: str
    provision_identifier: str
    reason: str


@dataclass(frozen=True, slots=True)
class RouterDraft:
    """Untrusted router output: the provisions it believes fit, ranked."""

    choices: tuple[RouterChoiceDraft, ...]


class RouterUnavailable(Exception):
    """The router could not produce a decision."""


@runtime_checkable
class ProvisionRouter(Protocol):
    """Select catalogue provisions for a described problem, or raise."""

    def route(self, *, problem: str, catalogue: Sequence[CataloguedProvision]) -> RouterDraft:
        """Return an untrusted draft, or raise `RouterUnavailable`."""


@dataclass(frozen=True, slots=True)
class RouteChoice:
    """A provision the router selected, validated against the catalogue.

    Every field is the catalogue's own canonical value, not the model's
    phrasing, so the router can never alter a provision's identity — only pick
    from what is indexed. `reason` is the router's short rationale, shown so the
    choice is visible rather than magic.
    """

    act_title: str
    jurisdiction: str
    provision_identifier: str
    pinpoint: str
    heading: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class RoutedProvision:
    """The router chose exactly one provision."""

    choice: RouteChoice


@dataclass(frozen=True, slots=True)
class RouteCandidates:
    """Two or three provisions could fit; the user chooses."""

    choices: tuple[RouteChoice, ...]


@dataclass(frozen=True, slots=True)
class RouteRefused:
    """No provision to research, with a typed reason."""

    code: RouteRefusalCode


#: The deterministic outcome of validating a router draft against the catalogue.
RouteDecision = RoutedProvision | RouteCandidates | RouteRefused


@dataclass(frozen=True, slots=True)
class RoutedAnswer:
    """A chosen provision and the answer the unchanged pipeline produced for it."""

    choice: RouteChoice
    answer: AnswerResult


#: What the routing service returns to a caller.
RouteOutcome = RoutedAnswer | RouteCandidates | RouteRefused


def _normalise_provision(identifier: str) -> str:
    """Reduce a provision identifier to a comparison key.

    The catalogue records ``s 55`` / ``s 5A``; a model may say ``section 55`` or
    ``55``. Strip the leading section marker and non-alphanumerics and lowercase
    the rest, so ``s 55`` / ``section 55`` / ``55`` all key to ``55`` — while
    ``5A`` and ``5`` stay distinct. Matching is still exact on that key; nothing
    is guessed.
    """

    lowered = identifier.strip().lower()
    lowered = re.sub(r"^(?:s|section|sec|reg|regulation)\b\.?\s*", "", lowered)
    # Preserve hyphens and slashes: they distinguish sub-ranges (s 1-5 ≠ s 15)
    # and slash-delimited identifiers. Strip only whitespace and other punctuation.
    return re.sub(r"[^a-z0-9/\-]", "", lowered)


def _catalogue_index(
    catalogue: Sequence[CataloguedProvision],
) -> dict[tuple[str, str], CataloguedProvision]:
    """Index the catalogue by (normalised act title, normalised provision)."""

    index: dict[tuple[str, str], CataloguedProvision] = {}
    for item in catalogue:
        key = (normalize_for_match(item.act_title), _normalise_provision(item.provision_identifier))
        index.setdefault(key, item)
    return index


def validate_route(draft: RouterDraft, catalogue: Sequence[CataloguedProvision]) -> RouteDecision:
    """Validate an untrusted router draft against the catalogue, deterministically.

    Every choice must resolve to a catalogue entry by (act, provision); a choice
    that does not — an invented Act, a section in the wrong Act, a near miss — is
    dropped, never coerced to a nearest match. Duplicates collapse and the list
    is capped. Zero survivors is a refusal; one is a routed provision; two or
    three are candidates for the user to confirm.
    """

    index = _catalogue_index(catalogue)
    chosen: list[RouteChoice] = []
    seen: set[tuple[str, str]] = set()
    for draft_choice in draft.choices:
        key = (
            normalize_for_match(draft_choice.act_title),
            _normalise_provision(draft_choice.provision_identifier),
        )
        item = index.get(key)
        if item is None or key in seen:
            continue
        seen.add(key)
        chosen.append(
            RouteChoice(
                act_title=item.act_title,
                jurisdiction=item.jurisdiction,
                provision_identifier=item.provision_identifier,
                pinpoint=item.pinpoint,
                heading=item.heading,
                reason=draft_choice.reason.strip()[:512],
            )
        )
        if len(chosen) >= MAX_ROUTE_CANDIDATES:
            break

    if not chosen:
        return RouteRefused(code=RouteRefusalCode.NO_MATCHING_PROVISION)
    if len(chosen) == 1:
        return RoutedProvision(choice=chosen[0])
    return RouteCandidates(choices=tuple(chosen))


class ProvisionRoutingService:
    """Route a described problem to a provision, then run the existing pipeline."""

    def __init__(
        self,
        *,
        router: ProvisionRouter,
        answer_service: GroundedAnswerService,
        catalogue: Sequence[CataloguedProvision],
        jurisdiction: str = WA_JURISDICTION,
    ) -> None:
        self._router = router
        self._answer = answer_service
        self._catalogue = tuple(catalogue)
        self._jurisdiction = jurisdiction

    def route(self, problem: str) -> RouteOutcome:
        """Route one problem to a provision, a candidate list, or a refusal."""

        # Scope gate first: an out-of-scope request is refused before the router
        # spends a model call, exactly as the answer pipeline refuses it.
        if classify_request_kind(problem) is not RequestKind.RESEARCH:
            return RouteRefused(code=RouteRefusalCode.REQUEST_OUT_OF_SCOPE)

        if not self._catalogue:
            return RouteRefused(code=RouteRefusalCode.CATALOGUE_EMPTY)

        try:
            draft = self._router.route(problem=problem, catalogue=self._catalogue)
        except RouterUnavailable as exc:
            _LOGGER.warning("provision router unavailable: %s", exc)
            return RouteRefused(code=RouteRefusalCode.ROUTER_UNAVAILABLE)
        except Exception:
            # Deliberately broad: a router that fails in any way has not chosen,
            # and must never degrade into a guess.
            _LOGGER.warning("provision router raised a fault", exc_info=True)
            return RouteRefused(code=RouteRefusalCode.ROUTER_UNAVAILABLE)

        decision = validate_route(draft, self._catalogue)
        if isinstance(decision, (RouteRefused, RouteCandidates)):
            return decision

        # Exactly one provision: run the unchanged answer pipeline for it.
        choice = decision.choice
        query = ResearchQuery(
            jurisdiction=choice.jurisdiction,
            act_title=choice.act_title,
            provision_identifier=choice.provision_identifier,
            pinpoint=choice.pinpoint,
        )
        answer = self._answer.answer(AnswerQuestion(question=problem, query=query))
        return RoutedAnswer(choice=choice, answer=answer)

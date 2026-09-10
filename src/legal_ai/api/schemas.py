"""Request and response bodies for the read-only research API."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from ..answering.models import AnswerRefused, GroundedAnswer, WithheldReason
from ..answering.provisions import CataloguedProvision
from ..answering.routing import (
    RouteCandidates,
    RouteChoice,
    RoutedAnswer,
    RouteRefusalCode,
    RouteRefused,
)
from ..answering.types import AnswerRefusalCode
from .settings import DISCLAIMER

_STRICT = ConfigDict(extra="forbid", strict=True, frozen=True)


#: Bounds mirroring the domain contract, applied at the HTTP boundary so an
#: over-long field is a 422 rather than an unhandled error deeper in.
_BoundedText = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=4096)]
_BoundedIdentifier = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=255)]


class ResearchRequestBody(BaseModel):
    """One deterministic research question bound to a specific provision."""

    model_config = _STRICT

    question: _BoundedText
    jurisdiction: _BoundedIdentifier
    act_title: _BoundedText
    provision_identifier: _BoundedIdentifier
    pinpoint: _BoundedIdentifier


class CitationBody(BaseModel):
    """A validated citation, rendered for transport."""

    model_config = _STRICT

    source_id: str
    act_title: str
    provision_identifier: str
    pinpoint: str
    source_version: str | None
    compilation_date: date | None
    official_source_url: str
    sha256: str
    quote: str | None


class PropositionBody(BaseModel):
    """A validated statement and the citation that supports it."""

    model_config = _STRICT

    statement: str
    citation: CitationBody


class WithheldBody(BaseModel):
    """One proposition dropped at level 3, named by pinpoint and reason only.

    The unverified statement text is deliberately absent: a statement that
    failed entailment is the confident-but-wrong content the pipeline exists to
    keep out of an answer, so it is never rendered — only the fact of its
    withholding and why.
    """

    model_config = _STRICT

    pinpoint: str
    reason: WithheldReason


class AnswerBody(BaseModel):
    """A fully cited answer, possibly partial.

    When `withheld` is non-empty the answer is partial: `partial` is true, the
    listed propositions are the ones that passed every check, and each withheld
    entry names a part that was dropped and why. The outcome stays ANSWERED — a
    partial answer is still an answer — while `partial` and `withheld` make the
    incompleteness explicit rather than silent.
    """

    model_config = _STRICT

    outcome: str = "ANSWERED"
    disclaimer: str
    propositions: tuple[PropositionBody, ...]
    partial: bool = False
    withheld: tuple[WithheldBody, ...] = ()


class RefusalBody(BaseModel):
    """A total refusal. Carries a typed code and no legal content whatsoever."""

    model_config = _STRICT

    outcome: str = "REFUSED"
    disclaimer: str
    code: AnswerRefusalCode


class HealthBody(BaseModel):
    """Liveness and configuration state."""

    model_config = _STRICT

    status: str
    corpus_configured: bool
    answer_model: str
    entailment_verified: bool
    disclaimer: str


def render_answer(answer: GroundedAnswer, disclaimer: str) -> AnswerBody:
    """Render a validated answer without re-deriving any legal content.

    Withheld propositions are rendered by pinpoint and reason only; their
    unverified statement text is never copied into the response.
    """

    return AnswerBody(
        partial=bool(answer.withheld),
        withheld=tuple(
            WithheldBody(pinpoint=item.pinpoint, reason=item.reason) for item in answer.withheld
        ),
        disclaimer=disclaimer,
        propositions=tuple(
            PropositionBody(
                statement=proposition.statement,
                citation=CitationBody(
                    source_id=proposition.citation.source_id,
                    act_title=proposition.citation.act_title,
                    provision_identifier=proposition.citation.provision_identifier,
                    pinpoint=proposition.citation.pinpoint,
                    source_version=proposition.citation.source_version,
                    compilation_date=proposition.citation.compilation_date,
                    official_source_url=proposition.citation.official_source_url,
                    sha256=proposition.citation.sha256,
                    quote=proposition.citation.quote,
                ),
            )
            for proposition in answer.propositions
        ),
    )


class ProvisionBody(BaseModel):
    """One indexed provision, offered for selection. Carries no text."""

    model_config = _STRICT

    provision_identifier: str
    pinpoint: str
    heading: str | None
    source_version: str | None


class ActBody(BaseModel):
    """One indexed Act and the provisions available within it."""

    model_config = _STRICT

    act_title: str
    jurisdiction: str
    provisions: tuple[ProvisionBody, ...]


class CorpusBody(BaseModel):
    """Everything the service can currently answer from."""

    model_config = _STRICT

    acts: tuple[ActBody, ...]
    provision_count: int
    disclaimer: str


def render_catalogue(catalogue: Sequence[CataloguedProvision]) -> CorpusBody:
    """Group the indexed provisions by Act for display."""

    grouped: dict[tuple[str, str], list[ProvisionBody]] = {}
    for item in catalogue:
        grouped.setdefault((item.act_title, item.jurisdiction), []).append(
            ProvisionBody(
                provision_identifier=item.provision_identifier,
                pinpoint=item.pinpoint,
                heading=item.heading,
                source_version=item.source_version,
            )
        )
    acts = tuple(
        ActBody(act_title=title, jurisdiction=jurisdiction, provisions=tuple(provisions))
        for (title, jurisdiction), provisions in sorted(grouped.items())
    )
    return CorpusBody(
        acts=acts,
        provision_count=len(catalogue),
        disclaimer=DISCLAIMER,
    )


class RouteRequestBody(BaseModel):
    """A described problem to route to a provision."""

    model_config = _STRICT

    problem: _BoundedText


class RouteChoiceBody(BaseModel):
    """A provision the router chose from the catalogue, with its rationale.

    Shown so the choice is visible rather than magic. The identity fields are the
    catalogue's own canonical values; `reason` is the router's short rationale.
    """

    model_config = _STRICT

    act_title: str
    jurisdiction: str
    provision_identifier: str
    pinpoint: str
    heading: str | None
    reason: str


class RoutedAnswerBody(BaseModel):
    """A routed provision and the pipeline's result for it."""

    model_config = _STRICT

    outcome: str = "ROUTED"
    disclaimer: str
    chosen: RouteChoiceBody
    #: The unchanged pipeline's own result for the chosen provision: an answer,
    #: possibly partial, or its own typed refusal.
    answer: AnswerBody | RefusalBody


class RouteCandidatesBody(BaseModel):
    """Two or three provisions could fit; the user confirms which to research."""

    model_config = _STRICT

    outcome: str = "CANDIDATES"
    disclaimer: str
    candidates: tuple[RouteChoiceBody, ...]


class RouteRefusalBody(BaseModel):
    """No provision to research, with a typed reason and no legal content."""

    model_config = _STRICT

    outcome: str = "REFUSED"
    disclaimer: str
    code: RouteRefusalCode


def _render_choice(choice: RouteChoice) -> RouteChoiceBody:
    return RouteChoiceBody(
        act_title=choice.act_title,
        jurisdiction=choice.jurisdiction,
        provision_identifier=choice.provision_identifier,
        pinpoint=choice.pinpoint,
        heading=choice.heading,
        reason=choice.reason,
    )


def render_routed_answer(routed: RoutedAnswer, disclaimer: str) -> RoutedAnswerBody:
    """Render a routed provision and the pipeline result it produced."""

    if isinstance(routed.answer, GroundedAnswer):
        answer: AnswerBody | RefusalBody = render_answer(routed.answer, disclaimer)
    elif isinstance(routed.answer, AnswerRefused):
        answer = RefusalBody(disclaimer=disclaimer, code=routed.answer.code)
    else:  # pragma: no cover - exhaustive guard
        answer = RefusalBody(disclaimer=disclaimer, code=AnswerRefusalCode.RESEARCH_TERMINATED)
    return RoutedAnswerBody(
        disclaimer=disclaimer, chosen=_render_choice(routed.choice), answer=answer
    )


def render_route_candidates(candidates: RouteCandidates, disclaimer: str) -> RouteCandidatesBody:
    """Render a short candidate list for the user to confirm."""

    return RouteCandidatesBody(
        disclaimer=disclaimer,
        candidates=tuple(_render_choice(choice) for choice in candidates.choices),
    )


def render_route_refusal(refused: RouteRefused, disclaimer: str) -> RouteRefusalBody:
    """Render a routing refusal."""

    return RouteRefusalBody(disclaimer=disclaimer, code=refused.code)

"""Request and response bodies for the read-only research API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from ..answering.models import GroundedAnswer
from ..answering.types import AnswerRefusalCode

_STRICT = ConfigDict(extra="forbid", strict=True, frozen=True)


class ResearchRequestBody(BaseModel):
    """One deterministic research question bound to a specific provision."""

    model_config = _STRICT

    question: str
    jurisdiction: str
    act_title: str
    provision_identifier: str
    pinpoint: str


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


class AnswerBody(BaseModel):
    """A fully cited answer."""

    model_config = _STRICT

    outcome: str = "ANSWERED"
    disclaimer: str
    propositions: tuple[PropositionBody, ...]


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
    """Render a validated answer without re-deriving any legal content."""

    return AnswerBody(
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

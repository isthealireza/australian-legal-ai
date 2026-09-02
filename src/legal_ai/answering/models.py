"""Grounded answering contracts.

`ModelDraft` and everything reachable from it is **untrusted model output**. It
is data, never instruction, and nothing in it is believed until
`validation.validate_draft` has checked every proposition against the exact
evidence packet it claims to rest on.

`GroundedAnswer` is only constructible from an already-validated draft, and
`AnswerRefused` carries no propositions and no citations at all: a refusal
cannot leak a legal statement, because there is nowhere to put one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from ..research.models import ExactIdentifier, ExactText, validate_wa_sha256
from .types import AnswerRefusalCode

_STRICT = ConfigDict(extra="forbid", strict=True, frozen=True)

MAX_PROPOSITIONS = 20

Sha256Digest = Annotated[
    str,
    StringConstraints(strict=True),
    AfterValidator(validate_wa_sha256),
]


class DraftCitation(BaseModel):
    """An untrusted citation asserted by the model."""

    model_config = _STRICT

    source_id: ExactIdentifier
    provision_identifier: ExactIdentifier
    pinpoint: ExactIdentifier
    sha256: Sha256Digest
    quote: ExactText | None = None


class DraftProposition(BaseModel):
    """One untrusted statement plus the citation the model says supports it."""

    model_config = _STRICT

    statement: ExactText
    citation: DraftCitation


class ModelDraft(BaseModel):
    """Structured, untrusted model output for one question."""

    model_config = _STRICT

    propositions: tuple[DraftProposition, ...]


class GroundedAnswerRequest(BaseModel):
    """The exact material handed to the answer model.

    The model receives the question and the validated evidence packet's own
    fields. It receives no tools, no corpus access, and no instruction channel.
    """

    model_config = _STRICT

    question: ExactText
    source_id: ExactIdentifier
    act_title: ExactText
    provision_identifier: ExactIdentifier
    pinpoint: ExactIdentifier
    provision_heading: ExactText | None
    source_version: ExactIdentifier | None
    compilation_date: date | None
    official_source_url: ExactText
    sha256: Sha256Digest
    source_content: bytes
    provision_text: str | None = None
    provision_sha256: Sha256Digest | None = None


class Citation(BaseModel):
    """A citation that has passed every deterministic check."""

    model_config = _STRICT

    source_id: ExactIdentifier
    act_title: ExactText
    provision_identifier: ExactIdentifier
    pinpoint: ExactIdentifier
    source_version: ExactIdentifier | None
    compilation_date: date | None
    official_source_url: ExactText
    sha256: Sha256Digest
    quote: ExactText | None


class Proposition(BaseModel):
    """A validated statement and its validated citation."""

    model_config = _STRICT

    statement: ExactText
    citation: Citation


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    """A fully validated, fully cited answer."""

    propositions: tuple[Proposition, ...]


@dataclass(frozen=True, slots=True)
class AnswerRefused:
    """A total refusal with a typed reason code and no legal content."""

    code: AnswerRefusalCode


AnswerResult = GroundedAnswer | AnswerRefused

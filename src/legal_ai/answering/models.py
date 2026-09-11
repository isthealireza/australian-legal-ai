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

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
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


class WithheldReason(StrEnum):
    """Why a single proposition was withheld from an otherwise cited answer."""

    #: The verifier ran and judged the statement not supported by the text.
    UNSUPPORTED = "UNSUPPORTED"
    #: The verifier could not return a verdict for this statement, so it is
    #: withheld rather than surfaced unverified — an unavailable check never
    #: degrades into a pass, at the level of one proposition just as before.
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class WithheldProposition:
    """A proposition that did not pass level 3 and was dropped from the answer.

    It carries the pinpoint it concerned and the reason it was withheld, so the
    answer can say plainly that a part was withheld and why. The unverified
    statement text is retained on the object for auditing but must never be
    rendered into a response: a statement that failed entailment is exactly the
    confident-but-wrong content the pipeline exists to keep out of an answer.
    """

    statement: str
    pinpoint: str
    reason: WithheldReason


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    """A fully validated, fully cited answer.

    Every proposition in `propositions` passed levels 1-3. `withheld` names any
    proposition dropped at level 3 while at least one other survived: the answer
    is partial, not total, and says so. When `withheld` is empty the answer is
    complete. An answer with no surviving proposition is never a `GroundedAnswer`
    — it is an `AnswerRefused`.
    """

    propositions: tuple[Proposition, ...]
    withheld: tuple[WithheldProposition, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AnswerRefused:
    """A total refusal with a typed reason code and no legal content."""

    code: AnswerRefusalCode


AnswerResult = GroundedAnswer | AnswerRefused

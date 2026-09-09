"""Fail-closed grounded answering pipeline (MVP_ROADMAP section 5).

    question
    -> deterministic retrieval (WaResearchService, audited)
    -> evidence packet
    -> digest-chained provision text, if any
    -> one structured model call
    -> deterministic citation validation (levels 1 and 2)
    -> optional independent entailment verification (level 3)
    -> answer or refusal

The model is called only after a packet has been validated and audited, is
handed only that packet's own fields plus text whose digest chains back to it,
and its output is believed only after every citation has been checked against
the packet. There is no path from a question to an answer that does not pass
through verified bytes.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum, auto

from ..research.models import ResearchQuery, WaEvidencePacket
from ..research.service import (
    ResearchRefused,
    ResearchTerminated,
    ResearchValidated,
    WaResearchService,
)
from ..research.types import ResearchRefusalCode as ResearchRefusalCodeType
from .errors import AnswerModelUnavailable
from .models import (
    AnswerRefused,
    AnswerResult,
    GroundedAnswer,
    GroundedAnswerRequest,
    ModelDraft,
    Proposition,
    WithheldProposition,
    WithheldReason,
)
from .protocol import LegalAnswerModel
from .provisions import DerivedProvision, DerivedProvisionStore, NullDerivedProvisionStore
from .scope import RequestKind, classify_request_kind
from .types import AnswerRefusalCode
from .validation import validate_draft
from .verification import EntailmentVerifier, VerifierUnavailable

_LOGGER = logging.getLogger("legal_ai.answering")

#: Upper bound on concurrent verifier calls for one answer.
MAX_VERIFIER_CONCURRENCY = 8


class _Verdict(Enum):
    """The level-3 outcome for one proposition. Internal to the pipeline."""

    SUPPORTED = auto()
    UNSUPPORTED = auto()
    UNVERIFIED = auto()


@dataclass(frozen=True, slots=True)
class AnswerQuestion:
    """One question bound to the exact provision it should be answered from."""

    question: str
    query: ResearchQuery


class GroundedAnswerService:
    """Compose audited retrieval, one model call, and deterministic validation."""

    def __init__(
        self,
        *,
        research: WaResearchService,
        model: LegalAnswerModel,
        provisions: DerivedProvisionStore | None = None,
        verifier: EntailmentVerifier | None = None,
    ) -> None:
        self._research = research
        self._model = model
        self._provisions = provisions if provisions is not None else NullDerivedProvisionStore()
        self._verifier = verifier

    def answer(self, request: AnswerQuestion) -> AnswerResult:
        """Return a fully cited answer, or refuse totally with a typed code."""

        # Scope gate first: the request kind is decided from the question text
        # before any retrieval or model call, so a contract/document review or a
        # drafting request is refused at near-zero cost and never reaches the
        # model. The refusal is audited exactly like an out-of-corpus one.
        if classify_request_kind(request.question) is not RequestKind.RESEARCH:
            recorded = self._research.audit_refusal(
                request.query, ResearchRefusalCodeType.REQUEST_OUT_OF_SCOPE
            )
            if not recorded:
                return AnswerRefused(code=AnswerRefusalCode.RESEARCH_TERMINATED)
            return AnswerRefused(code=AnswerRefusalCode.REQUEST_OUT_OF_SCOPE)

        result = self._research.research(request.query)
        if isinstance(result, ResearchTerminated):
            return AnswerRefused(code=AnswerRefusalCode.RESEARCH_TERMINATED)
        if isinstance(result, ResearchRefused):
            return AnswerRefused(code=AnswerRefusalCode.RESEARCH_REFUSED)
        if not isinstance(result, ResearchValidated):  # pragma: no cover - exhaustive guard
            return AnswerRefused(code=AnswerRefusalCode.RESEARCH_TERMINATED)

        packet = result.packet
        provision = self._provisions.resolve(packet)
        drafted = self._draft(request.question, packet, provision)
        if isinstance(drafted, AnswerRefusalCode):
            return AnswerRefused(code=drafted)
        draft, answered_by = drafted

        verified_text = provision.text if provision is not None else None
        validated = validate_draft(draft, packet, verified_text)
        if isinstance(validated, AnswerRefusalCode):
            return AnswerRefused(code=validated)

        return self._decide(validated, provision, answered_by)

    def _decide(
        self,
        propositions: tuple[Proposition, ...],
        provision: DerivedProvision | None,
        answered_by: str | None,
    ) -> AnswerResult:
        """Grade level 3 per proposition and assemble a partial or total result.

        The unit of the entailment decision is one proposition. Each is graded on
        its own; a supported one is kept, an unsupported or unverifiable one is
        dropped and named. If at least one survives, the answer is returned with
        the withheld ones recorded. If none survive, the whole answer is refused,
        exactly as before. The per-proposition check is no weaker than the old
        whole-answer one — only the unit of the decision changed.
        """

        verdicts = self._grade_each(propositions, provision, answered_by)

        kept: list[Proposition] = []
        withheld: list[WithheldProposition] = []
        for proposition, verdict in zip(propositions, verdicts, strict=True):
            if verdict is _Verdict.SUPPORTED:
                kept.append(proposition)
                continue
            reason = (
                WithheldReason.UNSUPPORTED
                if verdict is _Verdict.UNSUPPORTED
                else WithheldReason.UNVERIFIED
            )
            withheld.append(
                WithheldProposition(
                    statement=proposition.statement,
                    pinpoint=proposition.citation.pinpoint,
                    reason=reason,
                )
            )

        if not kept:
            # Nothing survived, so there is no partial answer to give. Refuse
            # totally, and prefer the unavailable code if any proposition could
            # not be verified — an outage must never read as a clean refusal.
            if any(verdict is _Verdict.UNVERIFIED for verdict in verdicts):
                return AnswerRefused(code=AnswerRefusalCode.ENTAILMENT_UNAVAILABLE)
            return AnswerRefused(code=AnswerRefusalCode.ENTAILMENT_UNSUPPORTED)

        return GroundedAnswer(propositions=tuple(kept), withheld=tuple(withheld))

    def _grade_each(
        self,
        propositions: tuple[Proposition, ...],
        provision: DerivedProvision | None,
        answered_by: str | None,
    ) -> tuple[_Verdict, ...]:
        """Return one verdict per proposition, in order.

        Grading is concurrent because run in sequence it dominates response
        time: a six-part answer would cost six round trips. Concurrency changes
        only the wall-clock cost, never a verdict. A verifier fault is confined
        to the one proposition it graded — it becomes that proposition's
        UNVERIFIED verdict, never a silent pass and never a verdict for another.
        """

        verifier = self._verifier
        if verifier is None:
            # Level 3 is opt-in. Without a verifier every proposition stands on
            # levels 1 and 2 alone, exactly as before.
            return tuple(_Verdict.SUPPORTED for _ in propositions)
        if provision is None:
            # A configured verifier with nothing to verify against has verified
            # nothing: every proposition is unverifiable, so none can be kept.
            return tuple(_Verdict.UNVERIFIED for _ in propositions)

        # A verifier that can exclude a provider is told which one produced the
        # statement, so a model is never asked to confirm its own output.
        excluding = getattr(verifier, "verify_excluding", None)

        def grade(proposition: Proposition) -> _Verdict:
            try:
                if callable(excluding):
                    supported: bool = excluding(
                        statement=proposition.statement,
                        provision_text=provision.text,
                        exclude=answered_by,
                    )
                else:
                    supported = verifier.verify(
                        statement=proposition.statement,
                        provision_text=provision.text,
                    )
            except VerifierUnavailable as exc:
                _LOGGER.warning("entailment verifier unavailable: %s", exc)
                return _Verdict.UNVERIFIED
            except Exception:
                # Deliberately broad: a verifier that fails in any way has not
                # verified this statement, and must never read as a pass.
                _LOGGER.warning("entailment verifier raised a fault", exc_info=True)
                return _Verdict.UNVERIFIED
            return _Verdict.SUPPORTED if supported else _Verdict.UNSUPPORTED

        workers = min(len(propositions), MAX_VERIFIER_CONCURRENCY)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return tuple(pool.map(grade, propositions))

    def _draft(
        self,
        question: str,
        packet: WaEvidencePacket,
        provision: DerivedProvision | None,
    ) -> tuple[ModelDraft, str | None] | AnswerRefusalCode:
        """Make the single model call, converting every failure into a refusal.

        Returns the draft and the provider that produced it, so entailment can
        be run somewhere else.
        """

        try:
            model_request = self._build_request(question, packet, provision)
        except Exception:
            # A request that cannot even be constructed is refused, never
            # raised out of the pipeline as an unhandled error.
            return AnswerRefusalCode.MODEL_OUTPUT_MALFORMED

        answered_by: str | None = None
        with_provider = getattr(self._model, "answer_with_provider", None)
        try:
            if callable(with_provider):
                outcome = with_provider(model_request)
                draft, answered_by = outcome.draft, outcome.provider
            else:
                draft = self._model.answer(model_request)
                answered_by = getattr(self._model, "name", None)
        except AnswerModelUnavailable as exc:
            # The refusal code the caller sees is deliberately coarse. Record
            # why here, or an intermittent provider fault is undiagnosable from
            # the outside. Nothing extra reaches the response.
            _LOGGER.warning("answer model unavailable: %s", exc)
            return AnswerRefusalCode.MODEL_UNAVAILABLE
        except Exception:
            # Deliberately broad: any adapter fault at all is fail-closed, and
            # never degrades into an uncited or model-memory answer.
            _LOGGER.warning("answer model raised an unexpected fault", exc_info=True)
            return AnswerRefusalCode.MODEL_UNAVAILABLE
        if not isinstance(draft, ModelDraft):
            return AnswerRefusalCode.MODEL_OUTPUT_MALFORMED
        return draft, answered_by

    @staticmethod
    def _build_request(
        question: str,
        packet: WaEvidencePacket,
        provision: DerivedProvision | None,
    ) -> GroundedAnswerRequest:
        """Assemble the exact material the model is allowed to see."""

        return GroundedAnswerRequest(
            question=question,
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
            provision_text=provision.text if provision is not None else None,
            provision_sha256=provision.sha256 if provision is not None else None,
        )

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

from ..research.models import ResearchQuery, WaEvidencePacket
from ..research.service import (
    ResearchRefused,
    ResearchTerminated,
    ResearchValidated,
    WaResearchService,
)
from .errors import AnswerModelUnavailable
from .models import (
    AnswerRefused,
    AnswerResult,
    GroundedAnswer,
    GroundedAnswerRequest,
    ModelDraft,
    Proposition,
)
from .protocol import LegalAnswerModel
from .provisions import DerivedProvision, DerivedProvisionStore, NullDerivedProvisionStore
from .types import AnswerRefusalCode
from .validation import validate_draft
from .verification import EntailmentVerifier, VerifierUnavailable

_LOGGER = logging.getLogger("legal_ai.answering")

#: Upper bound on concurrent verifier calls for one answer.
MAX_VERIFIER_CONCURRENCY = 8


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

        entailment = self._verify(validated, provision, answered_by)
        if entailment is not None:
            return AnswerRefused(code=entailment)
        return GroundedAnswer(propositions=validated)

    def _verify(
        self,
        propositions: tuple[Proposition, ...],
        provision: DerivedProvision | None,
        answered_by: str | None = None,
    ) -> AnswerRefusalCode | None:
        """Run level 3 when it is configured and possible. None means it passed.

        Each proposition is graded independently, so the calls are issued
        concurrently. Run in sequence they dominate response time: a six-part
        answer costs six round trips, which is minutes rather than seconds.
        Concurrency changes only the wall-clock cost, never the verdict — every
        proposition is still graded, and one failure still refuses everything.
        """

        verifier = self._verifier
        if verifier is None:
            return None
        if provision is None:
            # A configured verifier with nothing to verify against has not
            # verified anything. Skipping here would return an answer that is
            # indistinguishable from one that passed level 3.
            return AnswerRefusalCode.ENTAILMENT_UNAVAILABLE

        # A verifier that can exclude a provider is told which one produced the
        # statement, so a model is never asked to confirm its own output.
        excluding = getattr(verifier, "verify_excluding", None)

        def grade(proposition: Proposition) -> bool:
            if callable(excluding):
                supported: bool = excluding(
                    statement=proposition.statement,
                    provision_text=provision.text,
                    exclude=answered_by,
                )
                return supported
            return verifier.verify(
                statement=proposition.statement,
                provision_text=provision.text,
            )

        workers = min(len(propositions), MAX_VERIFIER_CONCURRENCY)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(grade, proposition) for proposition in propositions]
            try:
                verdicts = [future.result() for future in futures]
            except VerifierUnavailable as exc:
                _LOGGER.warning("entailment verifier unavailable: %s", exc)
                return AnswerRefusalCode.ENTAILMENT_UNAVAILABLE
            except Exception:
                # Deliberately broad: a verifier that fails in any way has not
                # verified anything, and must never read as a pass.
                _LOGGER.warning("entailment verifier raised a fault", exc_info=True)
                return AnswerRefusalCode.ENTAILMENT_UNAVAILABLE

        if not all(verdicts):
            return AnswerRefusalCode.ENTAILMENT_UNSUPPORTED
        return None

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

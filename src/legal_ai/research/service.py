"""Fail-closed WA research service over recorded fixtures (ADR 0013).

L0, deterministic and read-only. The service performs no live retrieval, no
network access, no model call, no persistence, and no external action. A
successful evaluation produces only a validated evidence packet.

Refusal and terminal results carry no `packet` attribute at all, so a partial
packet, a citation, or a legal proposition cannot be returned on any failing
path — the type system, not a convention, enforces it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .audit import ResearchAuditEvent, ResearchAuditSink
from .corpus import RecordedSourceCorpus, normalize_for_match
from .errors import AmbiguousSelection, RecordedCorpusError
from .models import PacketDraft, ResearchQuery, WaEvidencePacket
from .types import (
    WA_JURISDICTION,
    ResearchOutcome,
    ResearchRefusalCode,
    ResearchTerminalCode,
)
from .validation import validate_recorded_source


@dataclass(frozen=True, slots=True)
class ResearchValidated:
    """A validated, audited evidence packet."""

    packet: WaEvidencePacket


@dataclass(frozen=True, slots=True)
class ResearchRefused:
    """A total refusal with a typed reason code. The audit event was recorded."""

    code: ResearchRefusalCode


@dataclass(frozen=True, slots=True)
class ResearchTerminated:
    """A terminal failure. No audit event was recorded and nothing is returned."""

    code: ResearchTerminalCode = ResearchTerminalCode.AUDIT_SINK_UNAVAILABLE


ResearchResult = ResearchValidated | ResearchRefused | ResearchTerminated


class WaResearchService:
    """Deterministic WA research and evidence-packet validation."""

    def __init__(
        self,
        *,
        corpus: RecordedSourceCorpus,
        audit_sink: ResearchAuditSink | None,
    ) -> None:
        self._corpus = corpus
        self._audit_sink = audit_sink

    def research(self, query: ResearchQuery) -> ResearchResult:
        """Evaluate one query, audit the outcome, then return it.

        Both a validated outcome and an ordinary refusal attempt a structured
        audit event before returning. If the sink is absent, unavailable, or
        fails, the result is terminal `AUDIT_SINK_UNAVAILABLE`: no packet, no
        citation, no proposition, no partial result, and no claim that an audit
        event was emitted.
        """

        outcome = self._evaluate(query)
        if isinstance(outcome, ResearchRefusalCode):
            event = ResearchAuditEvent(
                outcome=ResearchOutcome.REFUSED,
                refusal_code=outcome,
                requested_jurisdiction=query.jurisdiction,
                requested_act_title=query.act_title,
                requested_provision_identifier=query.provision_identifier,
                requested_pinpoint=query.pinpoint,
            )
            if not self._record(event):
                return ResearchTerminated()
            return ResearchRefused(code=outcome)

        event = ResearchAuditEvent(
            outcome=ResearchOutcome.VALIDATED,
            refusal_code=None,
            requested_jurisdiction=query.jurisdiction,
            requested_act_title=query.act_title,
            requested_provision_identifier=query.provision_identifier,
            requested_pinpoint=query.pinpoint,
            source_id=outcome.source_id,
            sha256=outcome.sha256,
        )
        if not self._record(event):
            return ResearchTerminated()
        return ResearchValidated(packet=outcome.to_packet())

    def _evaluate(self, query: ResearchQuery) -> PacketDraft | ResearchRefusalCode:
        """Deterministically resolve one query without emitting anything."""

        if normalize_for_match(query.jurisdiction) != normalize_for_match(WA_JURISDICTION):
            return ResearchRefusalCode.JURISDICTION_MISMATCH
        try:
            source = self._corpus.select(query)
        except AmbiguousSelection:
            return ResearchRefusalCode.SELECTION_AMBIGUOUS
        except RecordedCorpusError:
            return ResearchRefusalCode.RETRIEVAL_MISSING
        if source is None:
            return ResearchRefusalCode.RETRIEVAL_MISSING
        return validate_recorded_source(query, source)

    def _record(self, event: ResearchAuditEvent) -> bool:
        """Attempt the required audit event. Any failure is fail-closed."""

        sink = self._audit_sink
        if sink is None:
            return False
        try:
            sink.record(event)
        except Exception:
            # Deliberately broad: an audit sink that fails in any way is
            # unavailable, and the dependent result must stop (governance §2.4).
            return False
        return True

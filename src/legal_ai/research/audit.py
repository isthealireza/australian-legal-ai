"""Injected research audit sink contract (ADR 0013 §5).

The sink is an interface only. This slice ships no production wiring and no
persistent audit storage; the sole implementation is an in-memory, test-only
double under `tests/support/`.
"""

from __future__ import annotations

from typing import Annotated, Protocol, runtime_checkable

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints, model_validator

from .models import validate_wa_sha256
from .types import ResearchOutcome, ResearchRefusalCode

_STRICT = ConfigDict(extra="forbid", strict=True, frozen=True)

_RequestedValue = Annotated[str, StringConstraints(strict=True, max_length=4096)]
_SourceId = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=255)]
_Digest = Annotated[str, StringConstraints(strict=True), AfterValidator(validate_wa_sha256)]


class ResearchAuditEvent(BaseModel):
    """One structured audit event describing a research evaluation.

    A refused evaluation carries a typed reason code and deliberately carries
    no source identity and no digest: a refusal never emits a citation, not
    even into the audit trail.
    """

    model_config = _STRICT

    outcome: ResearchOutcome
    refusal_code: ResearchRefusalCode | None
    requested_jurisdiction: _RequestedValue
    requested_act_title: _RequestedValue
    requested_provision_identifier: _RequestedValue
    requested_pinpoint: _RequestedValue
    source_id: _SourceId | None = None
    sha256: _Digest | None = None

    @model_validator(mode="after")
    def _require_consistent_event(self) -> ResearchAuditEvent:
        if self.outcome is ResearchOutcome.REFUSED:
            if self.refusal_code is None:
                raise ValueError("a refused outcome requires a typed refusal code")
            if self.source_id is not None or self.sha256 is not None:
                raise ValueError("a refused outcome must not carry a citation or digest")
        else:
            if self.refusal_code is not None:
                raise ValueError("a validated outcome must not carry a refusal code")
            if self.source_id is None or self.sha256 is None:
                raise ValueError("a validated outcome requires its source identity and digest")
        return self


@runtime_checkable
class ResearchAuditSink(Protocol):
    """Required audit sink for every research evaluation.

    Implementations raise if the event cannot be accepted. Any raised error is
    treated as a terminal `AUDIT_SINK_UNAVAILABLE` condition by the service.
    """

    def record(self, event: ResearchAuditEvent) -> None:
        """Accept one audit event, or raise if it cannot be recorded."""

"""Pydantic commands and frozen dataclass records for Phase 1 casework."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID
from zoneinfo import ZoneInfo, available_timezones

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from legal_ai.casework.types import (
    PHASE1_AUTHORITY_CEILINGS,
    ActionAuthorityLevel,
    ActorRef,
    AuditEventType,
    CaseType,
    ConfirmationMethod,
    DeadlineConfidence,
    DeadlinePrecision,
    DeadlineStatus,
    FactKind,
    FactStatus,
    IssueStatus,
    IssueType,
    Jurisdiction,
    MatterStatus,
    PartyEntityType,
    PartyRole,
    RiskLevel,
    TaskStatus,
    VerificationMethod,
)

_STRICT = ConfigDict(extra="forbid", strict=True, frozen=True)


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must contain a non-whitespace character")
    return value


NonBlankText = Annotated[
    str,
    StringConstraints(strict=True, min_length=1),
    AfterValidator(_reject_blank),
]
ShortNonBlank = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=64),
    AfterValidator(_reject_blank),
]
ReasonText = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=2000),
    AfterValidator(_reject_blank),
]
VerificationNote = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=2000),
    AfterValidator(_reject_blank),
]
VerificationSourceRef = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=512),
    AfterValidator(_reject_blank),
]

AUDIT_METADATA_ALLOWLIST: frozenset[str] = frozenset(
    {
        "command_type",
        "required_level",
        "ceiling",
        "from_status",
        "to_status",
        "party_id",
        "role",
        "fact_id",
        "from_fact_status",
        "to_fact_status",
        "issue_id",
        "from_issue_status",
        "to_issue_status",
        "task_id",
        "from_task_status",
        "to_task_status",
        "deadline_id",
        "precision",
        "timezone",
        "row_version",
        "entity_id",
        "playbook_key",
        "playbook_version_id",
        "playbook_version",
        "content_sha256",
        "candidate_count",
        "reason_code",
        "from_playbook_version_id",
        "to_playbook_version_id",
        "outcome_code",
        "evaluation_id",
        "question_id",
        "checklist_item_id",
        "correlation_id",
    }
)
_AUDIT_METADATA_MAX_BYTES = 4096
_AVAILABLE_TIMEZONES = frozenset(available_timezones())


def _validate_iana_timezone(value: str) -> str:
    if value not in _AVAILABLE_TIMEZONES:
        raise ValueError(f"invalid IANA timezone: {value}")
    # Ensure ZoneInfo can construct the zone on this platform.
    ZoneInfo(value)
    return value


IanaTimezone = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=64),
    AfterValidator(_reject_blank),
    AfterValidator(_validate_iana_timezone),
]


def validate_audit_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Reject non-allowlisted keys and payloads over 4 KiB UTF-8 JSON."""

    unknown = set(metadata) - AUDIT_METADATA_ALLOWLIST
    if unknown:
        keys = ", ".join(sorted(unknown))
        raise ValueError(f"audit metadata keys not allowlisted: {keys}")
    encoded = json.dumps(metadata, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(encoded) > _AUDIT_METADATA_MAX_BYTES:
        raise ValueError("audit metadata exceeds 4 KiB UTF-8 JSON limit")
    return metadata


class CreateMatterCommand(BaseModel):
    model_config = _STRICT

    title: NonBlankText
    summary: NonBlankText | None = None
    jurisdiction: Jurisdiction
    case_type: CaseType = CaseType.UNASSIGNED
    risk_level: RiskLevel = RiskLevel.R0
    action_authority_ceiling: ActionAuthorityLevel
    actor: ActorRef
    source_channel: ShortNonBlank
    correlation_id: UUID | None = None

    @field_validator("action_authority_ceiling")
    @classmethod
    def _phase1_ceiling(cls, value: ActionAuthorityLevel) -> ActionAuthorityLevel:
        if value not in PHASE1_AUTHORITY_CEILINGS:
            raise ValueError("action_authority_ceiling must be L0, L1, or L2")
        return value


class UpdateMatterCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    row_version: int = Field(strict=True, ge=1)
    actor: ActorRef
    source_channel: ShortNonBlank
    title: NonBlankText | None = None
    summary: NonBlankText | None = None
    jurisdiction: Jurisdiction | None = None
    case_type: CaseType | None = None
    risk_level: RiskLevel | None = None
    correlation_id: UUID | None = None

    @model_validator(mode="after")
    def _require_field_change(self) -> UpdateMatterCommand:
        if (
            self.title is None
            and self.summary is None
            and self.jurisdiction is None
            and self.case_type is None
            and self.risk_level is None
        ):
            raise ValueError("at least one updatable field must be provided")
        return self


class TransitionMatterCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    row_version: int = Field(strict=True, ge=1)
    target_status: MatterStatus
    actor: ActorRef
    source_channel: ShortNonBlank
    reason: ReasonText | None = None
    correlation_id: UUID | None = None


class ReopenMatterCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    row_version: int = Field(strict=True, ge=1)
    target_status: MatterStatus
    actor: ActorRef
    source_channel: ShortNonBlank
    reason: ReasonText
    correlation_id: UUID | None = None

    @field_validator("target_status")
    @classmethod
    def _reopen_targets(cls, value: MatterStatus) -> MatterStatus:
        if value not in {MatterStatus.ACTIVE, MatterStatus.RESEARCH_AND_DRAFT_ONLY}:
            raise ValueError("reopen target must be ACTIVE or RESEARCH_AND_DRAFT_ONLY")
        return value


class AddPartyCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    entity_type: PartyEntityType
    display_name: NonBlankText
    actor: ActorRef
    source_channel: ShortNonBlank
    correlation_id: UUID | None = None


class AssignRoleCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    party_id: UUID
    role: PartyRole
    actor: ActorRef
    source_channel: ShortNonBlank
    correlation_id: UUID | None = None


class AddFactCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    kind: FactKind
    statement: NonBlankText
    actor: ActorRef
    source_channel: ShortNonBlank
    status: FactStatus = FactStatus.ASSERTED
    source_ref: NonBlankText | None = None
    correlation_id: UUID | None = None

    @model_validator(mode="after")
    def _reject_verified_on_create(self) -> AddFactCommand:
        if self.status is FactStatus.VERIFIED:
            raise ValueError("facts cannot be created as VERIFIED")
        return self


class UpdateFactStatusCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    fact_id: UUID
    status: FactStatus
    actor: ActorRef
    source_channel: ShortNonBlank
    verified_by: ActorRef | None = None
    verified_at: datetime | None = None
    verification_method: VerificationMethod | None = None
    verification_source_ref: VerificationSourceRef | None = None
    verification_note: VerificationNote | None = None
    correlation_id: UUID | None = None

    @model_validator(mode="after")
    def _verification_invariants(self) -> UpdateFactStatusCommand:
        if self.status is FactStatus.VERIFIED:
            if self.verified_by is None or self.verified_at is None:
                raise ValueError("VERIFIED requires verified_by and verified_at")
            if self.verification_method is None or self.verification_note is None:
                raise ValueError("VERIFIED requires verification_method and verification_note")
            if self.verified_at.tzinfo is None or self.verified_at.utcoffset() is None:
                raise ValueError("verified_at must be timezone-aware")
            if self.verification_method is VerificationMethod.OPERATOR_ATTESTATION:
                return self
            if self.verification_source_ref is None:
                raise ValueError(
                    "DOCUMENT_REVIEW and THIRD_PARTY_CONFIRMATION require verification_source_ref"
                )
            return self
        if (
            self.verified_by is not None
            or self.verified_at is not None
            or self.verification_method is not None
            or self.verification_source_ref is not None
            or self.verification_note is not None
        ):
            raise ValueError("non-VERIFIED status requires all verification fields to be null")
        return self


class AddIssueCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    issue_type: IssueType
    question_or_topic: NonBlankText
    actor: ActorRef
    source_channel: ShortNonBlank
    status: IssueStatus = IssueStatus.OPEN
    correlation_id: UUID | None = None


class UpdateIssueStatusCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    issue_id: UUID
    status: IssueStatus
    actor: ActorRef
    source_channel: ShortNonBlank
    correlation_id: UUID | None = None


class AddDeadlineCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    source_description: NonBlankText
    jurisdiction: Jurisdiction
    confidence: DeadlineConfidence
    responsible_actor: ActorRef
    timezone: IanaTimezone
    precision: DeadlinePrecision
    actor: ActorRef
    source_channel: ShortNonBlank
    source_ref: NonBlankText | None = None
    due_date: date | None = None
    due_at: datetime | None = None
    status: DeadlineStatus = DeadlineStatus.OPEN
    human_confirmation_required: bool = True
    correlation_id: UUID | None = None

    @model_validator(mode="after")
    def _precision_xor(self) -> AddDeadlineCommand:
        if self.precision is DeadlinePrecision.DATE:
            if self.due_date is None or self.due_at is not None:
                raise ValueError("DATE precision requires due_date and null due_at")
            return self
        if self.due_at is None or self.due_date is not None:
            raise ValueError("DATETIME precision requires due_at and null due_date")
        if self.due_at.tzinfo is None or self.due_at.utcoffset() is None:
            raise ValueError("due_at must be timezone-aware")
        return self


class ConfirmDeadlineCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    deadline_id: UUID
    confirmed_by: ActorRef
    confirmation_method: ConfirmationMethod
    actor: ActorRef
    source_channel: ShortNonBlank
    confirmed_at: datetime | None = None
    correlation_id: UUID | None = None

    @field_validator("confirmed_at")
    @classmethod
    def _aware_confirmed_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("confirmed_at must be timezone-aware")
        return value


class UpdateDeadlineDueCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    deadline_id: UUID
    timezone: IanaTimezone
    precision: DeadlinePrecision
    actor: ActorRef
    source_channel: ShortNonBlank
    due_date: date | None = None
    due_at: datetime | None = None
    correlation_id: UUID | None = None

    @model_validator(mode="after")
    def _precision_xor(self) -> UpdateDeadlineDueCommand:
        if self.precision is DeadlinePrecision.DATE:
            if self.due_date is None or self.due_at is not None:
                raise ValueError("DATE precision requires due_date and null due_at")
            return self
        if self.due_at is None or self.due_date is not None:
            raise ValueError("DATETIME precision requires due_at and null due_date")
        if self.due_at.tzinfo is None or self.due_at.utcoffset() is None:
            raise ValueError("due_at must be timezone-aware")
        return self


class AddTaskCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    title: NonBlankText
    actor: ActorRef
    source_channel: ShortNonBlank
    status: TaskStatus = TaskStatus.OPEN
    deadline_id: UUID | None = None
    correlation_id: UUID | None = None


class UpdateTaskStatusCommand(BaseModel):
    model_config = _STRICT

    matter_id: UUID
    task_id: UUID
    status: TaskStatus
    actor: ActorRef
    source_channel: ShortNonBlank
    correlation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class MatterRecord:
    matter_id: UUID
    reference: str
    title: str
    summary: str | None
    status: MatterStatus
    jurisdiction: Jurisdiction
    case_type: CaseType
    risk_level: RiskLevel
    action_authority_ceiling: ActionAuthorityLevel
    row_version: int
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    assigned_playbook_version_id: UUID | None = None
    playbook_assigned_at: datetime | None = None
    playbook_assigned_by: str | None = None


@dataclass(frozen=True, slots=True)
class PartyRecord:
    party_id: UUID
    matter_id: UUID
    entity_type: PartyEntityType
    display_name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PartyRoleRecord:
    role_id: UUID
    matter_id: UUID
    party_id: UUID
    role: PartyRole
    created_at: datetime


@dataclass(frozen=True, slots=True)
class FactItemRecord:
    fact_id: UUID
    matter_id: UUID
    kind: FactKind
    status: FactStatus
    statement: str
    source_ref: str | None
    source_channel: str | None
    verified_by: str | None
    verified_at: datetime | None
    verification_method: VerificationMethod | None
    verification_source_ref: str | None
    verification_note: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class IssueRecord:
    issue_id: UUID
    matter_id: UUID
    issue_type: IssueType
    status: IssueStatus
    question_or_topic: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DeadlineRecord:
    deadline_id: UUID
    matter_id: UUID
    source_description: str
    source_ref: str | None
    jurisdiction: Jurisdiction
    confidence: DeadlineConfidence
    responsible_actor: str
    timezone: str
    precision: DeadlinePrecision
    due_date: date | None
    due_at: datetime | None
    status: DeadlineStatus
    human_confirmation_required: bool
    confirmed_by: str | None
    confirmed_at: datetime | None
    confirmation_method: ConfirmationMethod | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TaskRecord:
    task_id: UUID
    matter_id: UUID
    title: str
    status: TaskStatus
    deadline_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AuditEventRecord:
    event_id: UUID
    matter_id: UUID
    actor: str
    event_type: AuditEventType
    entity_type: str
    entity_id: UUID | None
    occurred_at: datetime
    correlation_id: UUID | None
    reason: str | None
    source_channel: str
    metadata: dict[str, Any]

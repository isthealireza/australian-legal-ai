"""Strict typed playbook definition payload (authoritative definition_json)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from legal_ai.casework.types import (
    ActionAuthorityLevel,
    ActorRef,
    CaseType,
    Jurisdiction,
    MatterStatus,
)
from legal_ai.playbooks.errors import PlaybookValidationError
from legal_ai.playbooks.hashing import content_sha256
from legal_ai.playbooks.rules import RuleGroup, RuleNode, parse_rule_node, validate_rule_tree
from legal_ai.playbooks.types import (
    MAX_AUDIT_METADATA_BYTES,
    MAX_DEFINITION_BYTES,
    MAX_ENUM_CODE_LENGTH,
    MAX_QUESTION_ID_LENGTH,
    MAX_TEXT_VALUE_LENGTH,
    PHASE2_AUTHORITY_CEILINGS,
    PLAYBOOK_AUDIT_METADATA_ALLOWLIST,
    PLAYBOOK_SCHEMA_VERSION,
    ChecklistItemStatus,
    DisqualifierOutcome,
    EvaluationOutcome,
    EvaluationReason,
    HumanApprovalKind,
    IntakeValueType,
    OperationalClass,
    PlaybookAuditEventType,
    PlaybookStatus,
    SourceReferenceCategory,
)

# Not strict: payloads are loaded from canonical JSON string enums.
_CFG = ConfigDict(extra="forbid", frozen=True)
_CMD = ConfigDict(extra="forbid", strict=True, frozen=True)


class IntakeQuestion(BaseModel):
    model_config = _CFG

    question_id: str = Field(min_length=1, max_length=MAX_QUESTION_ID_LENGTH)
    prompt: str = Field(min_length=1, max_length=MAX_TEXT_VALUE_LENGTH)
    value_type: IntakeValueType
    required: bool = False
    enum_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _enum_codes_match_type(self) -> IntakeQuestion:
        if self.value_type is IntakeValueType.ENUM:
            if not self.enum_codes:
                raise ValueError("ENUM questions require enum_codes")
            for code in self.enum_codes:
                if not code or len(code) > MAX_ENUM_CODE_LENGTH:
                    raise ValueError("invalid enum_code")
        elif self.enum_codes:
            raise ValueError("enum_codes only allowed for ENUM questions")
        return self


class DisqualifierRule(BaseModel):
    model_config = _CFG

    disqualifier_id: str = Field(min_length=1, max_length=64)
    outcome: DisqualifierOutcome
    rule: dict[str, Any]

    @field_validator("rule")
    @classmethod
    def _parse_rule(cls, value: dict[str, Any]) -> dict[str, Any]:
        parse_rule_node(value)
        return value


class EscalationRule(BaseModel):
    model_config = _CFG

    escalation_id: str = Field(min_length=1, max_length=64)
    outcome: DisqualifierOutcome
    rule: dict[str, Any]

    @field_validator("rule")
    @classmethod
    def _parse_rule(cls, value: dict[str, Any]) -> dict[str, Any]:
        parse_rule_node(value)
        return value


class EvidenceChecklistItem(BaseModel):
    model_config = _CFG

    checklist_item_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=MAX_TEXT_VALUE_LENGTH)
    description: str = Field(min_length=1, max_length=MAX_TEXT_VALUE_LENGTH)
    default_status: ChecklistItemStatus = ChecklistItemStatus.MISSING


class SourceReferenceSlot(BaseModel):
    model_config = _CFG

    category: SourceReferenceCategory
    description: str = Field(min_length=1, max_length=MAX_TEXT_VALUE_LENGTH)
    jurisdiction: Jurisdiction
    provenance_sha256: str | None = None
    frl_register_id: str | None = None
    notes: str | None = Field(default=None, max_length=MAX_TEXT_VALUE_LENGTH)


class FallbackBehaviour(BaseModel):
    model_config = _CFG

    prefer_status: MatterStatus = MatterStatus.RESEARCH_AND_DRAFT_ONLY
    require_human_review: bool = True
    description: str = Field(min_length=1, max_length=MAX_TEXT_VALUE_LENGTH)


class AllowedTransition(BaseModel):
    model_config = _CFG

    from_status: MatterStatus
    to_status: MatterStatus


class PlaybookDefinitionPayload(BaseModel):
    """Authoritative schema_version=1 definition payload."""

    model_config = _CFG

    schema_version: int = PLAYBOOK_SCHEMA_VERSION
    display_name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    operational_class: OperationalClass
    jurisdiction_codes: tuple[Jurisdiction, ...] = Field(min_length=1)
    supported_case_types: tuple[CaseType, ...] = Field(min_length=1)
    max_action_authority_level: ActionAuthorityLevel
    eligibility: dict[str, Any]
    intake_questions: tuple[IntakeQuestion, ...] = ()
    required_fields: tuple[str, ...] = ()
    disqualifiers: tuple[DisqualifierRule, ...] = ()
    escalation_rules: tuple[EscalationRule, ...] = ()
    evidence_checklist: tuple[EvidenceChecklistItem, ...] = ()
    allowed_matter_transitions: tuple[AllowedTransition, ...] = ()
    required_human_approvals: tuple[HumanApprovalKind, ...] = ()
    required_source_references: tuple[SourceReferenceSlot, ...] = ()
    fallback_behaviour: FallbackBehaviour

    @field_validator("schema_version")
    @classmethod
    def _schema_version(cls, value: int) -> int:
        if value != PLAYBOOK_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {PLAYBOOK_SCHEMA_VERSION}")
        return value

    @field_validator("max_action_authority_level")
    @classmethod
    def _authority(cls, value: ActionAuthorityLevel) -> ActionAuthorityLevel:
        if value not in PHASE2_AUTHORITY_CEILINGS:
            raise ValueError("max_action_authority_level must be L0, L1, or L2")
        return value

    @field_validator("eligibility")
    @classmethod
    def _eligibility(cls, value: dict[str, Any]) -> dict[str, Any]:
        parse_rule_node(value)
        return value

    @model_validator(mode="after")
    def _size_and_class(self) -> PlaybookDefinitionPayload:
        payload = self.to_canonical_dict()
        encoded = __import__("json").dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_DEFINITION_BYTES:
            raise ValueError("definition payload exceeds size limit")
        if (
            self.operational_class is OperationalClass.CASEWORK_JURISDICTION_BOUND
            and Jurisdiction.UNKNOWN in self.jurisdiction_codes
            and len(self.jurisdiction_codes) == 1
        ):
            raise ValueError("jurisdiction-bound playbook cannot be UNKNOWN-only")
        return self

    def eligibility_rule(self) -> RuleNode:
        return parse_rule_node(self.eligibility)

    def to_canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def content_sha256(self) -> str:
        return content_sha256(self.to_canonical_dict())


def validate_definition_payload(data: dict[str, Any]) -> PlaybookDefinitionPayload:
    try:
        payload = PlaybookDefinitionPayload.model_validate(data)
    except Exception as exc:  # noqa: BLE001 — normalize to domain error
        raise PlaybookValidationError(str(exc)) from exc
    validate_rule_tree(payload.eligibility_rule())
    for disqualifier in payload.disqualifiers:
        validate_rule_tree(parse_rule_node(disqualifier.rule))
    for escalation in payload.escalation_rules:
        validate_rule_tree(parse_rule_node(escalation.rule))
    return payload


# Ensure recursive RuleGroup models are fully built.
RuleGroup.model_rebuild()


def validate_playbook_audit_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Reject non-allowlisted keys and payloads over 4 KiB UTF-8 JSON."""

    unknown = set(metadata) - PLAYBOOK_AUDIT_METADATA_ALLOWLIST
    if unknown:
        keys = ", ".join(sorted(unknown))
        raise ValueError(f"playbook audit metadata keys not allowlisted: {keys}")
    encoded = json.dumps(metadata, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(encoded) > MAX_AUDIT_METADATA_BYTES:
        raise ValueError("playbook audit metadata exceeds 4 KiB UTF-8 JSON limit")
    return metadata


@dataclass(frozen=True, slots=True)
class PlaybookVersionRecord:
    playbook_version_id: UUID
    playbook_key: str
    version: int
    status: PlaybookStatus
    schema_version: int
    definition_json: dict[str, Any]
    content_sha256: str
    row_version: int
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    activated_by: str | None
    activated_at: datetime | None
    effective_from: datetime | None
    retired_by: str | None
    retired_at: datetime | None
    retirement_reason_code: str | None


@dataclass(frozen=True, slots=True)
class PlaybookAuditEventRecord:
    event_id: UUID
    playbook_key: str
    version: int
    playbook_version_id: UUID
    actor: str
    event_type: PlaybookAuditEventType
    occurred_at: datetime
    correlation_id: UUID | None
    row_version_after: int | None
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SeedDraftResult:
    version: PlaybookVersionRecord
    already_present: bool


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    evaluation_id: UUID
    matter_id: UUID
    occurred_at: datetime
    actor: str
    outcome_code: EvaluationOutcome
    reason_code: EvaluationReason
    selected_playbook_version_id: UUID | None
    matter_row_version_observed: int
    notes: str | None
    correlation_id: UUID | None


@dataclass(frozen=True, slots=True)
class IntakeAnswerRecord:
    matter_id: UUID
    playbook_version_id: UUID
    question_id: str
    value_type: IntakeValueType
    value_boolean: bool | None
    value_text: str | None
    value_date: date | None
    value_enum_code: str | None
    answered_by: str
    answered_at: datetime
    row_version: int


@dataclass(frozen=True, slots=True)
class ChecklistStateRecord:
    matter_id: UUID
    playbook_version_id: UUID
    checklist_item_id: str
    status: ChecklistItemStatus
    note: str | None
    updated_by: str
    updated_at: datetime
    row_version: int


class CreateDraftCommand(BaseModel):
    model_config = _CMD

    playbook_key: str = Field(min_length=1, max_length=128)
    version: int = Field(strict=True, ge=1)
    display_name: str = Field(min_length=1, max_length=200)
    definition: dict[str, Any]
    actor: ActorRef
    correlation_id: UUID | None = None


class UpdateDraftCommand(BaseModel):
    model_config = _CMD

    playbook_version_id: UUID
    row_version: int = Field(strict=True, ge=1)
    definition: dict[str, Any]
    actor: ActorRef
    correlation_id: UUID | None = None


class ActivateVersionCommand(BaseModel):
    model_config = _CMD

    playbook_version_id: UUID
    row_version: int = Field(strict=True, ge=1)
    actor: ActorRef
    effective_from: datetime | None = None
    correlation_id: UUID | None = None


class RetireVersionCommand(BaseModel):
    model_config = _CMD

    playbook_version_id: UUID
    row_version: int = Field(strict=True, ge=1)
    actor: ActorRef
    retirement_reason_code: str = Field(min_length=1, max_length=64)
    correlation_id: UUID | None = None


class AssignPlaybookCommand(BaseModel):
    model_config = _CMD

    matter_id: UUID
    playbook_version_id: UUID
    row_version: int = Field(strict=True, ge=1)
    actor: ActorRef
    source_channel: str = Field(min_length=1, max_length=64)
    facts: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID | None = None


class RejectAssignmentCommand(BaseModel):
    model_config = _CMD

    matter_id: UUID
    playbook_version_id: UUID | None = None
    row_version: int = Field(strict=True, ge=1)
    actor: ActorRef
    source_channel: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=2000)
    facts: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID | None = None


class ApplyFallbackCommand(BaseModel):
    model_config = _CMD

    matter_id: UUID
    row_version: int = Field(strict=True, ge=1)
    actor: ActorRef
    source_channel: str = Field(min_length=1, max_length=64)
    target_status: MatterStatus
    outcome_code: EvaluationOutcome
    reason_code: EvaluationReason
    candidate_version_ids: tuple[UUID, ...] = ()
    notes: str | None = Field(default=None, max_length=512)
    correlation_id: UUID | None = None


class MarkUnsupportedCommand(BaseModel):
    model_config = _CMD

    matter_id: UUID
    row_version: int = Field(strict=True, ge=1)
    actor: ActorRef
    source_channel: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=2000)
    correlation_id: UUID | None = None


class UpgradePlaybookCommand(BaseModel):
    model_config = _CMD

    matter_id: UUID
    target_playbook_version_id: UUID
    row_version: int = Field(strict=True, ge=1)
    actor: ActorRef
    source_channel: str = Field(min_length=1, max_length=64)
    facts: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID | None = None


class RecordBlockingDisqualifierCommand(BaseModel):
    model_config = _CMD

    matter_id: UUID
    row_version: int = Field(strict=True, ge=1)
    actor: ActorRef
    source_channel: str = Field(min_length=1, max_length=64)
    disqualifier_id: str = Field(min_length=1, max_length=64)
    outcome_code: EvaluationOutcome = EvaluationOutcome.BLOCKING_DISQUALIFIER_WHILE_PINNED
    facts: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=512)
    correlation_id: UUID | None = None


class UpsertIntakeAnswerCommand(BaseModel):
    model_config = _CMD

    matter_id: UUID
    question_id: str = Field(min_length=1, max_length=64)
    value_type: IntakeValueType
    actor: ActorRef
    source_channel: str = Field(min_length=1, max_length=64)
    value_boolean: bool | None = None
    value_text: str | None = Field(default=None, max_length=512)
    value_date: date | None = None
    value_enum_code: str | None = Field(default=None, max_length=64)
    expected_row_version: int | None = Field(default=None, strict=True, ge=1)
    correlation_id: UUID | None = None


class UpsertChecklistStateCommand(BaseModel):
    model_config = _CMD

    matter_id: UUID
    checklist_item_id: str = Field(min_length=1, max_length=64)
    status: ChecklistItemStatus
    actor: ActorRef
    source_channel: str = Field(min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=512)
    expected_row_version: int | None = Field(default=None, strict=True, ge=1)
    correlation_id: UUID | None = None

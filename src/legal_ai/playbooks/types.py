"""Playbook domain enums and shared aliases."""

from enum import StrEnum

from legal_ai.casework.types import (
    ActionAuthorityLevel,
    ActorRef,
    CaseType,
    Jurisdiction,
    MatterStatus,
)

PLAYBOOK_SCHEMA_VERSION = 1
MAX_DEFINITION_BYTES = 65_536
MAX_RULE_DEPTH = 4
MAX_RULE_NODES = 64
MAX_IN_LIST_SIZE = 32
MAX_TEXT_VALUE_LENGTH = 512
MAX_ENUM_CODE_LENGTH = 64
MAX_QUESTION_ID_LENGTH = 64
MAX_NOTES_LENGTH = 512
MAX_AUDIT_METADATA_BYTES = 4096


class PlaybookStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class OperationalClass(StrEnum):
    CASEWORK_JURISDICTION_BOUND = "CASEWORK_JURISDICTION_BOUND"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"


class RuleGroupOp(StrEnum):
    ALL = "ALL"
    ANY = "ANY"


class RuleComparator(StrEnum):
    EQ = "EQ"
    NE = "NE"
    IN = "IN"
    NOT_IN = "NOT_IN"
    IS_NULL = "IS_NULL"
    IS_NOT_NULL = "IS_NOT_NULL"
    IS_TRUE = "IS_TRUE"
    IS_FALSE = "IS_FALSE"


class RuleResult(StrEnum):
    MATCH = "MATCH"
    NO_MATCH = "NO_MATCH"
    UNKNOWN = "UNKNOWN"


class IntakeValueType(StrEnum):
    BOOLEAN = "BOOLEAN"
    TEXT = "TEXT"
    DATE = "DATE"
    ENUM = "ENUM"


class ChecklistItemStatus(StrEnum):
    PROVIDED = "PROVIDED"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    HUMAN_VERIFICATION_REQUIRED = "HUMAN_VERIFICATION_REQUIRED"


class DisqualifierOutcome(StrEnum):
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    RESEARCH_AND_DRAFT_ONLY = "RESEARCH_AND_DRAFT_ONLY"
    EMERGENCY_SERVICE_DIRECTION = "EMERGENCY_SERVICE_DIRECTION"
    EXTERNAL_LAWYER_ESCALATION = "EXTERNAL_LAWYER_ESCALATION"
    COMPLETE_REFUSAL = "COMPLETE_REFUSAL"


class EvaluationOutcome(StrEnum):
    NO_CANDIDATES = "NO_CANDIDATES"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    UNKNOWN_ELIGIBILITY = "UNKNOWN_ELIGIBILITY"
    BLOCKING_DISQUALIFIER = "BLOCKING_DISQUALIFIER"
    ASSIGNMENT_REJECTED = "ASSIGNMENT_REJECTED"
    BLOCKING_DISQUALIFIER_WHILE_PINNED = "BLOCKING_DISQUALIFIER_WHILE_PINNED"
    ASSIGNED = "ASSIGNED"
    UPGRADED = "UPGRADED"


class EvaluationReason(StrEnum):
    NO_ACTIVE_MATCH = "NO_ACTIVE_MATCH"
    MULTIPLE_ACTIVE_MATCHES = "MULTIPLE_ACTIVE_MATCHES"
    UNKNOWN_MATERIAL_ELIGIBILITY = "UNKNOWN_MATERIAL_ELIGIBILITY"
    DISQUALIFIER_MATCHED = "DISQUALIFIER_MATCHED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    HUMAN_ASSIGNED = "HUMAN_ASSIGNED"
    HUMAN_UPGRADED = "HUMAN_UPGRADED"
    CLOSED_MATTER = "CLOSED_MATTER"
    INCOMPATIBLE = "INCOMPATIBLE"


class HumanApprovalKind(StrEnum):
    ASSIGNMENT = "ASSIGNMENT"
    STATUS_TO_ACTIVE = "STATUS_TO_ACTIVE"
    CHECKLIST_COMPLETE = "CHECKLIST_COMPLETE"


class PlaybookAuditEventType(StrEnum):
    PLAYBOOK_DRAFT_CREATED = "PLAYBOOK_DRAFT_CREATED"
    PLAYBOOK_DRAFT_UPDATED = "PLAYBOOK_DRAFT_UPDATED"
    PLAYBOOK_DRAFT_SEED_NOOP = "PLAYBOOK_DRAFT_SEED_NOOP"
    PLAYBOOK_ACTIVATION_DENIED = "PLAYBOOK_ACTIVATION_DENIED"
    PLAYBOOK_ACTIVATED = "PLAYBOOK_ACTIVATED"
    PLAYBOOK_RETIRED = "PLAYBOOK_RETIRED"


class SourceReferenceCategory(StrEnum):
    LEGISLATION = "LEGISLATION"
    REGULATOR_GUIDANCE = "REGULATOR_GUIDANCE"
    COURT_FORM = "COURT_FORM"
    INSURER_PROCESS = "INSURER_PROCESS"
    OTHER_OFFICIAL = "OTHER_OFFICIAL"


PHASE2_CASE_TYPES: frozenset[CaseType] = frozenset(
    {
        CaseType.UNASSIGNED,
        CaseType.UNSUPPORTED,
        CaseType.SUPPORTED_PENDING_PLAYBOOK,
        CaseType.MOTOR_VEHICLE_PROPERTY_DAMAGE,
    }
)

PHASE2_AUTHORITY_CEILINGS: frozenset[ActionAuthorityLevel] = frozenset(
    {
        ActionAuthorityLevel.L0,
        ActionAuthorityLevel.L1,
        ActionAuthorityLevel.L2,
    }
)

ALLOWLISTED_MATTER_FIELDS: frozenset[str] = frozenset(
    {
        "matter.jurisdiction",
        "matter.case_type",
        "matter.status",
        "matter.risk_level",
    }
)

# Intake and flag fields are validated dynamically against question/flag ids.
INTAKE_FIELD_PREFIX = "intake."
FLAG_FIELD_PREFIX = "flags."

PLAYBOOK_AUDIT_METADATA_ALLOWLIST: frozenset[str] = frozenset(
    {
        "command_type",
        "content_sha256",
        "row_version",
        "reason_code",
        "grounding_error_type",
        "schema_version",
        "from_status",
        "to_status",
    }
)

__all__ = [
    "ALLOWLISTED_MATTER_FIELDS",
    "ActorRef",
    "ActionAuthorityLevel",
    "CaseType",
    "ChecklistItemStatus",
    "DisqualifierOutcome",
    "EvaluationOutcome",
    "EvaluationReason",
    "FLAG_FIELD_PREFIX",
    "HumanApprovalKind",
    "INTAKE_FIELD_PREFIX",
    "IntakeValueType",
    "Jurisdiction",
    "MAX_AUDIT_METADATA_BYTES",
    "MAX_DEFINITION_BYTES",
    "MAX_ENUM_CODE_LENGTH",
    "MAX_IN_LIST_SIZE",
    "MAX_NOTES_LENGTH",
    "MAX_QUESTION_ID_LENGTH",
    "MAX_RULE_DEPTH",
    "MAX_RULE_NODES",
    "MAX_TEXT_VALUE_LENGTH",
    "MatterStatus",
    "OperationalClass",
    "PHASE2_AUTHORITY_CEILINGS",
    "PHASE2_CASE_TYPES",
    "PLAYBOOK_AUDIT_METADATA_ALLOWLIST",
    "PLAYBOOK_SCHEMA_VERSION",
    "PlaybookAuditEventType",
    "PlaybookStatus",
    "RuleComparator",
    "RuleGroupOp",
    "RuleResult",
    "SourceReferenceCategory",
]

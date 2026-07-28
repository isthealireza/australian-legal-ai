"""Casework domain enums and shared type aliases."""

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, StringConstraints


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must contain a non-whitespace character")
    return value


ActorRef = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[a-zA-Z0-9_.:@-]{1,128}$"),
    AfterValidator(_reject_blank),
]


class Jurisdiction(StrEnum):
    AU_CTH = "AU-CTH"
    AU_ACT = "AU-ACT"
    AU_NSW = "AU-NSW"
    AU_NT = "AU-NT"
    AU_QLD = "AU-QLD"
    AU_SA = "AU-SA"
    AU_TAS = "AU-TAS"
    AU_VIC = "AU-VIC"
    AU_WA = "AU-WA"
    UNKNOWN = "UNKNOWN"


JURISDICTION_LABELS: dict[Jurisdiction, str] = {
    Jurisdiction.AU_CTH: "Commonwealth of Australia",
    Jurisdiction.AU_ACT: "Australian Capital Territory",
    Jurisdiction.AU_NSW: "New South Wales",
    Jurisdiction.AU_NT: "Northern Territory",
    Jurisdiction.AU_QLD: "Queensland",
    Jurisdiction.AU_SA: "South Australia",
    Jurisdiction.AU_TAS: "Tasmania",
    Jurisdiction.AU_VIC: "Victoria",
    Jurisdiction.AU_WA: "Western Australia",
    Jurisdiction.UNKNOWN: "Unknown / not yet determined",
}


class MatterStatus(StrEnum):
    INTAKE_INCOMPLETE = "INTAKE_INCOMPLETE"
    INTAKE_COMPLETE = "INTAKE_COMPLETE"
    RESEARCH_AND_DRAFT_ONLY = "RESEARCH_AND_DRAFT_ONLY"
    ACTIVE = "ACTIVE"
    WAITING = "WAITING"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class CaseType(StrEnum):
    UNASSIGNED = "UNASSIGNED"
    UNSUPPORTED = "UNSUPPORTED"
    SUPPORTED_PENDING_PLAYBOOK = "SUPPORTED_PENDING_PLAYBOOK"
    MOTOR_VEHICLE_PROPERTY_DAMAGE = "MOTOR_VEHICLE_PROPERTY_DAMAGE"


class RiskLevel(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class ActionAuthorityLevel(StrEnum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"
    L6 = "L6"


PHASE1_AUTHORITY_CEILINGS: frozenset[ActionAuthorityLevel] = frozenset(
    {
        ActionAuthorityLevel.L0,
        ActionAuthorityLevel.L1,
        ActionAuthorityLevel.L2,
    }
)


class PartyEntityType(StrEnum):
    NATURAL_PERSON = "NATURAL_PERSON"
    ORGANISATION = "ORGANISATION"


class PartyRole(StrEnum):
    PRIMARY_SUBJECT = "PRIMARY_SUBJECT"
    CLIENT = "CLIENT"
    COUNTERPARTY = "COUNTERPARTY"
    WITNESS = "WITNESS"
    INSURER = "INSURER"
    GOVERNMENT_AGENCY = "GOVERNMENT_AGENCY"
    REPRESENTATIVE = "REPRESENTATIVE"
    OTHER = "OTHER"


class FactKind(StrEnum):
    USER_ALLEGATION = "USER_ALLEGATION"
    OBSERVED = "OBSERVED"
    IMPORTED_STATEMENT = "IMPORTED_STATEMENT"
    DERIVED = "DERIVED"
    ASSUMPTION = "ASSUMPTION"
    UNKNOWN_ITEM = "UNKNOWN_ITEM"


class FactStatus(StrEnum):
    ASSERTED = "ASSERTED"
    DISPUTED = "DISPUTED"
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"


class VerificationMethod(StrEnum):
    OPERATOR_ATTESTATION = "OPERATOR_ATTESTATION"
    DOCUMENT_REVIEW = "DOCUMENT_REVIEW"
    THIRD_PARTY_CONFIRMATION = "THIRD_PARTY_CONFIRMATION"


class IssueType(StrEnum):
    FACTUAL = "FACTUAL"
    LEGAL_QUESTION = "LEGAL_QUESTION"
    ADMINISTRATIVE = "ADMINISTRATIVE"


class IssueStatus(StrEnum):
    OPEN = "OPEN"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"
    WITHDRAWN = "WITHDRAWN"


class TaskStatus(StrEnum):
    OPEN = "OPEN"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class DeadlinePrecision(StrEnum):
    DATE = "DATE"
    DATETIME = "DATETIME"


class DeadlineStatus(StrEnum):
    OPEN = "OPEN"
    MET = "MET"
    CANCELLED = "CANCELLED"


class DeadlineConfidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConfirmationMethod(StrEnum):
    OPERATOR_ATTESTATION = "OPERATOR_ATTESTATION"
    EXTERNAL_NOTICE_RECORDED = "EXTERNAL_NOTICE_RECORDED"


class AuditEventType(StrEnum):
    MATTER_CREATED = "MATTER_CREATED"
    MATTER_STATUS_CHANGED = "MATTER_STATUS_CHANGED"
    MATTER_REOPENED = "MATTER_REOPENED"
    MATTER_UPDATED = "MATTER_UPDATED"
    PARTY_ADDED = "PARTY_ADDED"
    PARTY_ROLE_ASSIGNED = "PARTY_ROLE_ASSIGNED"
    FACT_ADDED = "FACT_ADDED"
    FACT_STATUS_CHANGED = "FACT_STATUS_CHANGED"
    ISSUE_ADDED = "ISSUE_ADDED"
    ISSUE_STATUS_CHANGED = "ISSUE_STATUS_CHANGED"
    TASK_ADDED = "TASK_ADDED"
    TASK_STATUS_CHANGED = "TASK_STATUS_CHANGED"
    DEADLINE_ADDED = "DEADLINE_ADDED"
    DEADLINE_CONFIRMED = "DEADLINE_CONFIRMED"
    DEADLINE_DUE_VALUE_CHANGED = "DEADLINE_DUE_VALUE_CHANGED"
    DEADLINE_CONFIRMATION_CLEARED = "DEADLINE_CONFIRMATION_CLEARED"
    ACTION_DENIED = "ACTION_DENIED"
    PLAYBOOK_ASSIGNED = "PLAYBOOK_ASSIGNED"
    PLAYBOOK_ASSIGNMENT_REJECTED = "PLAYBOOK_ASSIGNMENT_REJECTED"
    PLAYBOOK_FALLBACK_APPLIED = "PLAYBOOK_FALLBACK_APPLIED"
    PLAYBOOK_UPGRADE_REQUESTED = "PLAYBOOK_UPGRADE_REQUESTED"
    PLAYBOOK_UPGRADED = "PLAYBOOK_UPGRADED"
    PLAYBOOK_UNSUPPORTED_MARKED = "PLAYBOOK_UNSUPPORTED_MARKED"
    PLAYBOOK_BLOCKING_DISQUALIFIER = "PLAYBOOK_BLOCKING_DISQUALIFIER"
    INTAKE_ANSWER_UPSERTED = "INTAKE_ANSWER_UPSERTED"
    CHECKLIST_STATE_UPSERTED = "CHECKLIST_STATE_UPSERTED"


_AUTHORITY_ORDER: dict[ActionAuthorityLevel, int] = {
    ActionAuthorityLevel.L0: 0,
    ActionAuthorityLevel.L1: 1,
    ActionAuthorityLevel.L2: 2,
    ActionAuthorityLevel.L3: 3,
    ActionAuthorityLevel.L4: 4,
    ActionAuthorityLevel.L5: 5,
    ActionAuthorityLevel.L6: 6,
}


def authority_rank(level: ActionAuthorityLevel) -> int:
    return _AUTHORITY_ORDER[level]

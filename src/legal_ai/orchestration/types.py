"""Orchestration domain enums and shared type aliases.

This module describes how *engineering work* on this repository is coordinated
between a coordinator agent and controlled worker agents. It is deliberately
not a product runtime capability: nothing here is reachable from the legal
answering pipeline, and nothing here can grant the product's model a tool.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, StringConstraints


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must contain a non-whitespace character")
    return value


OrchestrationId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[A-Za-z0-9_.:-]{1,128}$"),
    AfterValidator(_reject_blank),
]

ExactLine = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=2000),
    AfterValidator(_reject_blank),
]

ExactBody = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=20000),
    AfterValidator(_reject_blank),
]


class WorkerRole(StrEnum):
    """Who may do what in a bounded task."""

    COORDINATOR = "COORDINATOR"
    IMPLEMENTER = "IMPLEMENTER"
    REVIEWER = "REVIEWER"
    EVALUATOR = "EVALUATOR"


class AccessMode(StrEnum):
    """How much of the working tree a role may change."""

    READ_ONLY = "READ_ONLY"
    REVIEW_ONLY = "REVIEW_ONLY"
    SCOPED_WRITE = "SCOPED_WRITE"


class TaskState(StrEnum):
    """Bounded-task lifecycle states.

    These mirror the Orca orchestration task statuses so a task node in this
    module and the Orca task row it corresponds to never disagree.
    """

    PENDING = "PENDING"
    READY = "READY"
    DISPATCHED = "DISPATCHED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


TERMINAL_TASK_STATES: frozenset[TaskState] = frozenset({TaskState.COMPLETED})

MAX_ATTEMPTS_CEILING = 3
"""A bounded task gets a bounded number of attempts. Shared by the contract
model and the state machine so a direct state-machine caller cannot exceed the
allowance a contract would have capped."""


class MessageType(StrEnum):
    """Message kinds exchanged through the orchestration transport."""

    STATUS = "STATUS"
    HEARTBEAT = "HEARTBEAT"
    QUESTION = "QUESTION"
    ANSWER = "ANSWER"
    ESCALATION = "ESCALATION"
    DECISION_GATE = "DECISION_GATE"
    WORKER_DONE = "WORKER_DONE"


class WorkerOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class FindingSeverity(StrEnum):
    """Review finding classes required by CLAUDE.md."""

    BLOCKING = "BLOCKING"
    VALID_NON_BLOCKING = "VALID_NON_BLOCKING"
    UNSUPPORTED = "UNSUPPORTED"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"


class AutonomousActivity(StrEnum):
    """Routine engineering the coordinator performs without asking the owner."""

    TASK_DECOMPOSITION = "TASK_DECOMPOSITION"
    WORKER_DISPATCH = "WORKER_DISPATCH"
    READ_ONLY_REVIEW = "READ_ONLY_REVIEW"
    TEST_EXECUTION = "TEST_EXECUTION"
    BOUNDED_RETRY = "BOUNDED_RETRY"
    DETERMINISTIC_VALIDATION = "DETERMINISTIC_VALIDATION"
    IN_SCOPE_DOCUMENTATION = "IN_SCOPE_DOCUMENTATION"
    WORKER_FINDING_INTEGRATION = "WORKER_FINDING_INTEGRATION"


class ProtectedDecision(StrEnum):
    """Decisions that always stop for an explicit owner instruction."""

    SCOPE_CHANGE = "SCOPE_CHANGE"
    GOVERNANCE_CONTROL_CHANGE = "GOVERNANCE_CONTROL_CHANGE"
    REAL_CLIENT_DATA_OR_SECRETS = "REAL_CLIENT_DATA_OR_SECRETS"
    EXTERNAL_PUBLICATION_OR_DEPLOYMENT = "EXTERNAL_PUBLICATION_OR_DEPLOYMENT"
    PROTECTED_BRANCH_MERGE = "PROTECTED_BRANCH_MERGE"
    LEGAL_CONTENT_ACCEPTANCE = "LEGAL_CONTENT_ACCEPTANCE"
    MATERIAL_EXTERNAL_SIDE_EFFECT = "MATERIAL_EXTERNAL_SIDE_EFFECT"


class ProductCapability(StrEnum):
    """Capabilities the product's legal-answering model must never receive.

    A bounded task contract that names any of these is rejected at construction
    time. The list restates ENGINEERING_WORKFLOW.md rule 13 and
    PROJECT_GOVERNANCE.md section 7 as executable code.
    """

    SHELL = "SHELL"
    BROWSER = "BROWSER"
    EMAIL = "EMAIL"
    UNRESTRICTED_NETWORK = "UNRESTRICTED_NETWORK"
    UNRESTRICTED_FILESYSTEM = "UNRESTRICTED_FILESYSTEM"
    PERSISTENT_MEMORY = "PERSISTENT_MEMORY"
    SELF_MODIFICATION = "SELF_MODIFICATION"
    CONTRACT_BUILDER = "CONTRACT_BUILDER"

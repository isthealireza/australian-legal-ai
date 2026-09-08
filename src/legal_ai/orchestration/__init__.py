"""Orchestration foundation: typed bounded-task contracts and worker roles.

This package models how engineering work on this repository is coordinated
between a coordinator agent and controlled worker agents. It is a repository
governance module, not a product runtime capability:

- nothing here is imported by the legal answering pipeline or the HTTP API;
- a bounded task contract can never grant the product's model a tool
  (`ProductCapability` is a deny list, enforced at construction);
- worker messages and results are untrusted data, validated before belief;
- write access is denied by default and widened only by an explicit,
  canonical, per-task file allowlist.

See `docs/adr/0016-agent-orchestration-foundation.md`.
"""

from legal_ai.orchestration.approvals import (
    APPROVAL_BOUNDARY_RECORDED_ON,
    AUTONOMOUS_ACTIVITIES,
    PROTECTED_DECISIONS,
    assert_autonomous,
    requires_owner_approval,
)
from legal_ai.orchestration.contracts import (
    ORCHESTRATION_AUTHORITY_CEILING,
    AcceptedWorkerResult,
    BoundedTaskContract,
    ReviewFinding,
    WorkerMessage,
    WorkerResult,
    validate_worker_result,
)
from legal_ai.orchestration.errors import (
    InvalidTaskTransitionError,
    OrchestrationError,
    OrchestrationValidationError,
    OwnerApprovalRequired,
    RoleAccessDenied,
    TaskGraphError,
    UnknownRoleError,
    WorkerResultRejected,
)
from legal_ai.orchestration.graph import MAX_TASKS, TaskGraph, build_task_graph
from legal_ai.orchestration.roles import (
    DEFAULT_ROLE_CONFIGURATIONS,
    RoleConfiguration,
    assert_write_allowed,
    normalise_repo_path,
    resolve_role_configuration,
)
from legal_ai.orchestration.state_machine import (
    allowed_targets,
    assert_task_transition_allowed,
)
from legal_ai.orchestration.types import (
    MAX_ATTEMPTS_CEILING,
    TERMINAL_TASK_STATES,
    AccessMode,
    AutonomousActivity,
    FindingSeverity,
    MessageType,
    ProductCapability,
    ProtectedDecision,
    TaskState,
    WorkerOutcome,
    WorkerRole,
)

__all__ = [
    "APPROVAL_BOUNDARY_RECORDED_ON",
    "AUTONOMOUS_ACTIVITIES",
    "DEFAULT_ROLE_CONFIGURATIONS",
    "MAX_ATTEMPTS_CEILING",
    "MAX_TASKS",
    "ORCHESTRATION_AUTHORITY_CEILING",
    "PROTECTED_DECISIONS",
    "TERMINAL_TASK_STATES",
    "AcceptedWorkerResult",
    "AccessMode",
    "AutonomousActivity",
    "BoundedTaskContract",
    "FindingSeverity",
    "InvalidTaskTransitionError",
    "MessageType",
    "OrchestrationError",
    "OrchestrationValidationError",
    "OwnerApprovalRequired",
    "ProductCapability",
    "ProtectedDecision",
    "ReviewFinding",
    "RoleAccessDenied",
    "RoleConfiguration",
    "TaskGraph",
    "TaskGraphError",
    "TaskState",
    "UnknownRoleError",
    "WorkerMessage",
    "WorkerOutcome",
    "WorkerResult",
    "WorkerResultRejected",
    "WorkerRole",
    "allowed_targets",
    "assert_autonomous",
    "assert_task_transition_allowed",
    "assert_write_allowed",
    "build_task_graph",
    "normalise_repo_path",
    "requires_owner_approval",
    "resolve_role_configuration",
    "validate_worker_result",
]

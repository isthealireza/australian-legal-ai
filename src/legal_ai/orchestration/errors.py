"""Typed errors for the orchestration foundation."""

from __future__ import annotations

from legal_ai.orchestration.types import (
    AccessMode,
    ProtectedDecision,
    TaskState,
    WorkerRole,
)


class OrchestrationError(Exception):
    """Base class for orchestration foundation failures."""


class OrchestrationValidationError(OrchestrationError):
    """Input failed orchestration domain validation."""


class InvalidTaskTransitionError(OrchestrationError):
    """Task state transition is forbidden."""

    def __init__(self, *, current: TaskState, target: TaskState, reason: str) -> None:
        self.current = current
        self.target = target
        self.reason = reason
        super().__init__(f"transition forbidden: {current.value} -> {target.value}: {reason}")


class UnknownRoleError(OrchestrationError):
    """No configuration is registered for the requested role."""

    def __init__(self, *, role: WorkerRole | str) -> None:
        self.role = role
        super().__init__(f"no role configuration registered for {role!r}")


class RoleAccessDenied(OrchestrationError):
    """A role attempted an access its configuration does not grant."""

    def __init__(self, *, role: WorkerRole, access_mode: AccessMode, path: str) -> None:
        self.role = role
        self.access_mode = access_mode
        self.path = path
        super().__init__(f"{role.value} ({access_mode.value}) may not write {path!r}")


class TaskGraphError(OrchestrationError):
    """The task DAG is not a bounded, acyclic, self-consistent graph."""


class WorkerResultRejected(OrchestrationError):
    """An untrusted worker result failed validation against its contract."""

    def __init__(self, *, task_id: str, reason: str) -> None:
        self.task_id = task_id
        self.reason = reason
        super().__init__(f"worker result for {task_id} rejected: {reason}")


class OwnerApprovalRequired(OrchestrationError):
    """The coordinator reached a protected decision and must stop."""

    def __init__(self, *, decision: ProtectedDecision | str) -> None:
        self.decision = decision
        super().__init__(f"owner approval required before proceeding: {decision}")

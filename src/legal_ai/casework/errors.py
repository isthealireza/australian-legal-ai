"""Typed errors for the Generic Casework Core."""

from __future__ import annotations

from legal_ai.casework.types import ActionAuthorityLevel, MatterStatus


class CaseworkError(Exception):
    """Base class for casework domain failures."""


class CaseworkValidationError(CaseworkError):
    """Input failed domain validation."""


class NotFoundError(CaseworkError):
    """Requested matter-scoped entity was not found."""


class InvalidTransitionError(CaseworkError):
    """Matter status transition is forbidden."""

    def __init__(self, *, current: MatterStatus, target: MatterStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"transition forbidden: {current.value} -> {target.value}")


class ClosedMatterMutationError(CaseworkError):
    """Mutation attempted on a CLOSED matter outside ReopenMatter."""


class ConcurrencyConflictError(CaseworkError):
    """Optimistic concurrency version mismatch."""


class ActionAuthorityDenied(CaseworkError):
    """Command exceeds the matter authority ceiling or Phase 1 L0–L2 limit."""

    def __init__(
        self,
        *,
        required: ActionAuthorityLevel,
        ceiling: ActionAuthorityLevel | None,
        command_type: str,
    ) -> None:
        self.required = required
        self.ceiling = ceiling
        self.command_type = command_type
        ceiling_label = ceiling.value if ceiling is not None else "none"
        super().__init__(
            f"action denied: {command_type} requires {required.value}, ceiling={ceiling_label}"
        )


class AuditWriteFailed(CaseworkError):
    """Audit sink write failed; dependent action must not succeed."""


class ReferenceAllocationError(CaseworkError):
    """Human-readable matter reference could not be allocated uniquely."""


class CrossMatterViolationError(CaseworkError):
    """Attempted relationship or query crossed matter boundaries."""

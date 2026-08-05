"""Playbook domain errors."""

from __future__ import annotations

from legal_ai.casework.types import ActionAuthorityLevel


class PlaybookError(Exception):
    """Base playbook error."""


class PlaybookValidationError(PlaybookError):
    """Definition or command failed validation."""


class PlaybookNotFoundError(PlaybookError):
    """Requested playbook version was not found."""


class PlaybookConcurrencyConflictError(PlaybookError):
    """Optimistic concurrency conflict on a draft playbook version."""


class GroundingUnavailable(PlaybookError):
    """Production grounding validator is unavailable; activation fail-closed."""


class GroundingValidationFailed(PlaybookError):
    """Grounding references failed validation."""


class SeedHashConflictError(PlaybookError):
    """Existing draft seed hash differs from the fixture hash."""


class SeedAlreadyPresent(PlaybookError):
    """Identical draft seed already present (idempotent no-op signal)."""


class TransitionRequiredError(PlaybookError):
    """Fallback recorded but matter status cannot transition under Phase 1 rules."""

    def __init__(self, message: str, *, evaluation_id: object | None = None) -> None:
        super().__init__(message)
        self.evaluation_id = evaluation_id


class PlaybookAssignmentError(PlaybookError):
    """Assignment or upgrade rejected for policy reasons."""


class PlaybookAuthorityDenied(PlaybookError):
    """Required authority exceeds the effective playbook/matter ceiling."""

    def __init__(
        self,
        *,
        required: ActionAuthorityLevel,
        effective_ceiling: ActionAuthorityLevel,
        command_type: str,
    ) -> None:
        super().__init__(
            f"{command_type} requires {required.value} but effective ceiling is "
            f"{effective_ceiling.value}"
        )
        self.required = required
        self.effective_ceiling = effective_ceiling
        self.command_type = command_type


class PlaybookAuditWriteFailed(PlaybookError):
    """Playbook audit insert failed; mutation must roll back."""

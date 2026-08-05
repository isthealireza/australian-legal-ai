"""Deterministic matter lifecycle transitions for Phase 1."""

from __future__ import annotations

from legal_ai.casework.errors import InvalidTransitionError
from legal_ai.casework.types import CaseType, MatterStatus

_ALLOWED: dict[MatterStatus, frozenset[MatterStatus]] = {
    MatterStatus.INTAKE_INCOMPLETE: frozenset(
        {
            MatterStatus.INTAKE_COMPLETE,
            MatterStatus.RESEARCH_AND_DRAFT_ONLY,
        }
    ),
    MatterStatus.INTAKE_COMPLETE: frozenset(
        {
            MatterStatus.ACTIVE,
            MatterStatus.RESEARCH_AND_DRAFT_ONLY,
        }
    ),
    MatterStatus.ACTIVE: frozenset(
        {
            MatterStatus.WAITING,
            MatterStatus.HUMAN_REVIEW_REQUIRED,
            MatterStatus.RESEARCH_AND_DRAFT_ONLY,
            MatterStatus.RESOLVED,
        }
    ),
    MatterStatus.RESEARCH_AND_DRAFT_ONLY: frozenset(
        {
            MatterStatus.HUMAN_REVIEW_REQUIRED,
            MatterStatus.RESOLVED,
        }
    ),
    MatterStatus.WAITING: frozenset(
        {
            MatterStatus.ACTIVE,
            MatterStatus.HUMAN_REVIEW_REQUIRED,
            MatterStatus.RESOLVED,
        }
    ),
    MatterStatus.HUMAN_REVIEW_REQUIRED: frozenset(
        {
            MatterStatus.ACTIVE,
            MatterStatus.RESEARCH_AND_DRAFT_ONLY,
            MatterStatus.RESOLVED,
        }
    ),
    MatterStatus.RESOLVED: frozenset({MatterStatus.CLOSED}),
    MatterStatus.CLOSED: frozenset(
        {
            MatterStatus.ACTIVE,
            MatterStatus.RESEARCH_AND_DRAFT_ONLY,
        }
    ),
}


def assert_transition_allowed(
    *,
    current: MatterStatus,
    target: MatterStatus,
    case_type: CaseType,
    reopen: bool = False,
) -> None:
    """Raise InvalidTransitionError when the edge or guard fails."""

    allowed = _ALLOWED.get(current, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(current=current, target=target)

    if current is MatterStatus.CLOSED and not reopen:
        raise InvalidTransitionError(current=current, target=target)

    if current is MatterStatus.CLOSED and reopen:
        if target not in {
            MatterStatus.ACTIVE,
            MatterStatus.RESEARCH_AND_DRAFT_ONLY,
        }:
            raise InvalidTransitionError(current=current, target=target)
        return

    if (
        current is MatterStatus.INTAKE_COMPLETE
        and target is MatterStatus.ACTIVE
        and case_type is CaseType.UNSUPPORTED
    ):
        raise InvalidTransitionError(current=current, target=target)

    if (
        current is MatterStatus.INTAKE_INCOMPLETE
        and target is MatterStatus.RESEARCH_AND_DRAFT_ONLY
        and case_type is not CaseType.UNSUPPORTED
    ):
        raise InvalidTransitionError(current=current, target=target)


def allowed_targets(current: MatterStatus) -> frozenset[MatterStatus]:
    return _ALLOWED.get(current, frozenset())

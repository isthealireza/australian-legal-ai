"""Unit tests for matter state transitions."""

import pytest

from legal_ai.casework.errors import InvalidTransitionError
from legal_ai.casework.state_machine import allowed_targets, assert_transition_allowed
from legal_ai.casework.types import CaseType, MatterStatus


def test_intake_incomplete_to_complete_allowed() -> None:
    assert_transition_allowed(
        current=MatterStatus.INTAKE_INCOMPLETE,
        target=MatterStatus.INTAKE_COMPLETE,
        case_type=CaseType.UNASSIGNED,
    )


def test_intake_incomplete_to_research_only_allowed_for_unsupported() -> None:
    assert_transition_allowed(
        current=MatterStatus.INTAKE_INCOMPLETE,
        target=MatterStatus.RESEARCH_AND_DRAFT_ONLY,
        case_type=CaseType.UNSUPPORTED,
    )


def test_intake_incomplete_to_research_only_forbidden_when_not_unsupported() -> None:
    with pytest.raises(InvalidTransitionError):
        assert_transition_allowed(
            current=MatterStatus.INTAKE_INCOMPLETE,
            target=MatterStatus.RESEARCH_AND_DRAFT_ONLY,
            case_type=CaseType.UNASSIGNED,
        )


def test_intake_complete_to_active_forbidden_when_unsupported() -> None:
    with pytest.raises(InvalidTransitionError):
        assert_transition_allowed(
            current=MatterStatus.INTAKE_COMPLETE,
            target=MatterStatus.ACTIVE,
            case_type=CaseType.UNSUPPORTED,
        )


def test_intake_complete_to_research_only_allowed_for_unsupported() -> None:
    assert_transition_allowed(
        current=MatterStatus.INTAKE_COMPLETE,
        target=MatterStatus.RESEARCH_AND_DRAFT_ONLY,
        case_type=CaseType.UNSUPPORTED,
    )


def test_closed_to_waiting_forbidden() -> None:
    with pytest.raises(InvalidTransitionError):
        assert_transition_allowed(
            current=MatterStatus.CLOSED,
            target=MatterStatus.WAITING,
            case_type=CaseType.UNASSIGNED,
            reopen=True,
        )


def test_reopen_to_active_allowed() -> None:
    assert_transition_allowed(
        current=MatterStatus.CLOSED,
        target=MatterStatus.ACTIVE,
        case_type=CaseType.SUPPORTED_PENDING_PLAYBOOK,
        reopen=True,
    )


def test_resolved_to_closed_allowed() -> None:
    assert_transition_allowed(
        current=MatterStatus.RESOLVED,
        target=MatterStatus.CLOSED,
        case_type=CaseType.UNASSIGNED,
    )


def test_forbidden_skip_edge() -> None:
    with pytest.raises(InvalidTransitionError):
        assert_transition_allowed(
            current=MatterStatus.INTAKE_INCOMPLETE,
            target=MatterStatus.CLOSED,
            case_type=CaseType.UNASSIGNED,
        )


def test_allowed_targets_for_active() -> None:
    targets = allowed_targets(MatterStatus.ACTIVE)
    assert MatterStatus.WAITING in targets
    assert MatterStatus.CLOSED not in targets

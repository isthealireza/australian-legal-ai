"""The recorded owner autonomy boundary."""

from __future__ import annotations

import pytest

from legal_ai.orchestration.approvals import (
    AUTONOMOUS_ACTIVITIES,
    PROTECTED_DECISIONS,
    assert_autonomous,
    requires_owner_approval,
)
from legal_ai.orchestration.errors import OwnerApprovalRequired
from legal_ai.orchestration.types import AutonomousActivity, ProtectedDecision


@pytest.mark.parametrize("activity", list(AutonomousActivity))
def test_routine_engineering_proceeds_without_approval(
    activity: AutonomousActivity,
) -> None:
    assert requires_owner_approval(activity) is False
    assert_autonomous(activity)


@pytest.mark.parametrize("decision", list(ProtectedDecision))
def test_protected_decisions_never_become_automatic(decision: ProtectedDecision) -> None:
    assert requires_owner_approval(decision) is True
    with pytest.raises(OwnerApprovalRequired):
        assert_autonomous(decision)


def test_an_unrecognised_activity_fails_closed() -> None:
    assert requires_owner_approval("DELETE_THE_AUDIT_LOG") is True
    with pytest.raises(OwnerApprovalRequired):
        assert_autonomous("DELETE_THE_AUDIT_LOG")


def test_the_two_sets_are_disjoint_and_complete() -> None:
    assert AUTONOMOUS_ACTIVITIES == frozenset(AutonomousActivity)
    assert PROTECTED_DECISIONS == frozenset(ProtectedDecision)
    assert not {a.value for a in AUTONOMOUS_ACTIVITIES} & {d.value for d in PROTECTED_DECISIONS}

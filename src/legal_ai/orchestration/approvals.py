"""The owner-approved autonomy boundary, as executable configuration.

Recorded from an explicit owner decision on 2026-09-03: routine engineering and
orchestration proceed without asking, and a fixed set of protected decisions
never becomes automatic.

The classification fails closed. Only the activities enumerated in
`AUTONOMOUS_ACTIVITIES` are autonomous; anything else — including an activity
this module does not recognise — requires the owner.
"""

from __future__ import annotations

from legal_ai.orchestration.errors import OwnerApprovalRequired
from legal_ai.orchestration.types import AutonomousActivity, ProtectedDecision

APPROVAL_BOUNDARY_RECORDED_ON = "2026-09-03"

AUTONOMOUS_ACTIVITIES: frozenset[AutonomousActivity] = frozenset(AutonomousActivity)
"""Routine engineering the coordinator performs and reports, without pausing."""

PROTECTED_DECISIONS: frozenset[ProtectedDecision] = frozenset(ProtectedDecision)
"""Decisions that always stop for an explicit owner instruction."""


def requires_owner_approval(activity: AutonomousActivity | ProtectedDecision | str) -> bool:
    """Return whether `activity` must stop for the owner.

    An unrecognised value is treated as protected, not as autonomous.
    """

    if isinstance(activity, AutonomousActivity):
        return activity not in AUTONOMOUS_ACTIVITIES
    return True


def assert_autonomous(activity: AutonomousActivity | ProtectedDecision | str) -> None:
    """Raise `OwnerApprovalRequired` unless `activity` is inside the boundary."""

    if requires_owner_approval(activity):
        raise OwnerApprovalRequired(decision=activity)

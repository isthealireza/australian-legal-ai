"""Deterministic bounded-task lifecycle transitions.

Every edge is enumerated. An unknown current state has no outgoing edges, so an
unrecognised state fails closed rather than falling through to a permissive
default.
"""

from __future__ import annotations

from legal_ai.orchestration.errors import InvalidTaskTransitionError
from legal_ai.orchestration.types import MAX_ATTEMPTS_CEILING, TaskState

_ALLOWED: dict[TaskState, frozenset[TaskState]] = {
    TaskState.PENDING: frozenset({TaskState.READY, TaskState.BLOCKED}),
    TaskState.READY: frozenset({TaskState.DISPATCHED, TaskState.BLOCKED}),
    TaskState.DISPATCHED: frozenset({TaskState.COMPLETED, TaskState.FAILED, TaskState.BLOCKED}),
    TaskState.BLOCKED: frozenset({TaskState.READY, TaskState.FAILED}),
    TaskState.FAILED: frozenset({TaskState.READY}),
    TaskState.COMPLETED: frozenset(),
}


def allowed_targets(current: TaskState) -> frozenset[TaskState]:
    """Return the edges leaving `current`; empty for terminal or unknown states."""

    return _ALLOWED.get(current, frozenset())


def assert_task_transition_allowed(
    *,
    current: TaskState,
    target: TaskState,
    dependencies_satisfied: bool,
    attempt: int,
    max_attempts: int,
) -> None:
    """Raise `InvalidTaskTransitionError` when the edge or a guard fails.

    Guards:

    - a task only becomes `READY` once every dependency has completed;
    - a `FAILED` task only re-enters `READY` while attempts remain, so the
      bounded retry allowance cannot be exceeded by repeated retries.

    The attempt counters are checked against `MAX_ATTEMPTS_CEILING` here as well
    as in `BoundedTaskContract`, because this function is exported and a caller
    that never built a contract must not be able to grant itself more attempts.
    """

    if attempt < 1:
        raise InvalidTaskTransitionError(
            current=current, target=target, reason="attempt must be >= 1"
        )
    if not 1 <= max_attempts <= MAX_ATTEMPTS_CEILING:
        raise InvalidTaskTransitionError(
            current=current,
            target=target,
            reason=f"max_attempts must be 1..{MAX_ATTEMPTS_CEILING}",
        )
    if attempt > max_attempts:
        raise InvalidTaskTransitionError(
            current=current,
            target=target,
            reason=f"attempt {attempt} exceeds max_attempts {max_attempts}",
        )

    if target not in allowed_targets(current):
        raise InvalidTaskTransitionError(
            current=current, target=target, reason="edge is not defined"
        )

    if target is TaskState.READY and not dependencies_satisfied:
        raise InvalidTaskTransitionError(
            current=current, target=target, reason="dependencies are not satisfied"
        )

    if current is TaskState.FAILED and target is TaskState.READY and attempt >= max_attempts:
        raise InvalidTaskTransitionError(
            current=current,
            target=target,
            reason=f"retry allowance exhausted ({attempt}/{max_attempts})",
        )

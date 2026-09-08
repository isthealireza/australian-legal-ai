"""Bounded-task lifecycle transitions."""

from __future__ import annotations

import pytest

from legal_ai.orchestration.errors import InvalidTaskTransitionError
from legal_ai.orchestration.state_machine import (
    allowed_targets,
    assert_task_transition_allowed,
)
from legal_ai.orchestration.types import MAX_ATTEMPTS_CEILING, TaskState


def _assert(current: TaskState, target: TaskState, **overrides: object) -> None:
    kwargs: dict[str, object] = {
        "dependencies_satisfied": True,
        "attempt": 1,
        "max_attempts": 3,
    }
    kwargs.update(overrides)
    assert_task_transition_allowed(current=current, target=target, **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TaskState.PENDING, TaskState.READY),
        (TaskState.PENDING, TaskState.BLOCKED),
        (TaskState.READY, TaskState.DISPATCHED),
        (TaskState.READY, TaskState.BLOCKED),
        (TaskState.DISPATCHED, TaskState.COMPLETED),
        (TaskState.DISPATCHED, TaskState.FAILED),
        (TaskState.DISPATCHED, TaskState.BLOCKED),
        (TaskState.BLOCKED, TaskState.READY),
        (TaskState.BLOCKED, TaskState.FAILED),
        (TaskState.FAILED, TaskState.READY),
    ],
)
def test_declared_edges_are_allowed(current: TaskState, target: TaskState) -> None:
    _assert(current, target)


def test_every_state_is_enumerated() -> None:
    """A state missing from the table would silently have no legal exit."""

    for state in TaskState:
        assert isinstance(allowed_targets(state), frozenset)


def test_completed_is_terminal() -> None:
    assert allowed_targets(TaskState.COMPLETED) == frozenset()
    for target in TaskState:
        with pytest.raises(InvalidTaskTransitionError):
            _assert(TaskState.COMPLETED, target)


def test_undeclared_edge_is_refused() -> None:
    with pytest.raises(InvalidTaskTransitionError) as excinfo:
        _assert(TaskState.PENDING, TaskState.COMPLETED)
    assert "edge is not defined" in str(excinfo.value)


def test_ready_requires_satisfied_dependencies() -> None:
    with pytest.raises(InvalidTaskTransitionError) as excinfo:
        _assert(TaskState.PENDING, TaskState.READY, dependencies_satisfied=False)
    assert "dependencies are not satisfied" in str(excinfo.value)


def test_retry_allowance_is_bounded() -> None:
    _assert(TaskState.FAILED, TaskState.READY, attempt=2, max_attempts=3)
    with pytest.raises(InvalidTaskTransitionError) as excinfo:
        _assert(TaskState.FAILED, TaskState.READY, attempt=3, max_attempts=3)
    assert "retry allowance exhausted" in str(excinfo.value)


@pytest.mark.parametrize(("attempt", "max_attempts"), [(0, 3), (1, 0)])
def test_nonsensical_attempt_counters_are_refused(attempt: int, max_attempts: int) -> None:
    with pytest.raises(InvalidTaskTransitionError):
        _assert(
            TaskState.PENDING,
            TaskState.READY,
            attempt=attempt,
            max_attempts=max_attempts,
        )


def test_state_machine_enforces_the_retry_ceiling_independently() -> None:
    """The exported guard is callable without a contract, so it caps attempts too."""

    with pytest.raises(InvalidTaskTransitionError) as excinfo:
        _assert(TaskState.FAILED, TaskState.READY, attempt=1, max_attempts=999)
    assert f"1..{MAX_ATTEMPTS_CEILING}" in str(excinfo.value)


def test_attempt_may_not_exceed_its_own_allowance() -> None:
    with pytest.raises(InvalidTaskTransitionError) as excinfo:
        _assert(TaskState.PENDING, TaskState.READY, attempt=3, max_attempts=2)
    assert "exceeds max_attempts" in str(excinfo.value)

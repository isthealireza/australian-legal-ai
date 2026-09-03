"""The bounded, acyclic task DAG."""

from __future__ import annotations

import pytest

from legal_ai.orchestration.contracts import BoundedTaskContract
from legal_ai.orchestration.errors import TaskGraphError
from legal_ai.orchestration.graph import MAX_TASKS, build_task_graph
from legal_ai.orchestration.types import AccessMode, TaskState, WorkerRole


def contract(task_id: str, *deps: str) -> BoundedTaskContract:
    return BoundedTaskContract(
        task_id=task_id,
        title=f"Task {task_id}",
        objective=f"Do the work of {task_id}.",
        role=WorkerRole.REVIEWER,
        access_mode=AccessMode.REVIEW_ONLY,
        acceptance_criteria=("Findings are classified.",),
        rollback_instructions="No files change; nothing to roll back.",
        depends_on=frozenset(deps),
    )


def test_topological_order_is_deterministic_and_respects_dependencies() -> None:
    graph = build_task_graph(
        [contract("T4", "T2", "T3"), contract("T3"), contract("T2", "T1"), contract("T1")]
    )
    assert graph.topological_order == ("T1", "T3", "T2", "T4")
    again = build_task_graph(
        [contract("T1"), contract("T2", "T1"), contract("T3"), contract("T4", "T2", "T3")]
    )
    assert again.topological_order == graph.topological_order


def test_cycle_is_refused() -> None:
    with pytest.raises(TaskGraphError) as excinfo:
        build_task_graph([contract("A", "B"), contract("B", "A")])
    assert "cycle" in str(excinfo.value)


def test_unknown_dependency_is_refused() -> None:
    with pytest.raises(TaskGraphError) as excinfo:
        build_task_graph([contract("A", "MISSING")])
    assert "unknown task" in str(excinfo.value)


def test_duplicate_task_id_is_refused() -> None:
    with pytest.raises(TaskGraphError):
        build_task_graph([contract("A"), contract("A")])


def test_empty_and_oversized_graphs_are_refused() -> None:
    with pytest.raises(TaskGraphError):
        build_task_graph([])
    with pytest.raises(TaskGraphError):
        build_task_graph([contract(f"T{index}") for index in range(MAX_TASKS + 1)])


def test_ready_tasks_wait_for_their_dependencies() -> None:
    graph = build_task_graph([contract("T1"), contract("T2", "T1"), contract("T3")])
    pending = dict.fromkeys(("T1", "T2", "T3"), TaskState.PENDING)
    assert graph.ready_task_ids(pending) == ("T1", "T3")

    after_t1 = {**pending, "T1": TaskState.COMPLETED}
    # Topological order is ("T1", "T3", "T2"): T1 and T3 have no dependencies, so
    # they form the first layer and T2 follows. Readiness keeps that stable order.
    assert graph.topological_order == ("T1", "T3", "T2")
    assert graph.ready_task_ids(after_t1) == ("T3", "T2")


def test_a_failed_dependency_does_not_release_its_dependant() -> None:
    graph = build_task_graph([contract("T1"), contract("T2", "T1")])
    states = {"T1": TaskState.FAILED, "T2": TaskState.PENDING}
    assert graph.ready_task_ids(states) == ()


def test_state_map_must_cover_exactly_the_graph() -> None:
    graph = build_task_graph([contract("T1"), contract("T2")])
    with pytest.raises(TaskGraphError):
        graph.ready_task_ids({"T1": TaskState.PENDING})
    with pytest.raises(TaskGraphError):
        graph.ready_task_ids(
            {"T1": TaskState.PENDING, "T2": TaskState.PENDING, "T9": TaskState.PENDING}
        )


def test_contract_lookup_fails_closed() -> None:
    graph = build_task_graph([contract("T1")])
    with pytest.raises(TaskGraphError):
        graph.contract("T9")

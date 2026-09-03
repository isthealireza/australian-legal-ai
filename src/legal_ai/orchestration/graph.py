"""A bounded, acyclic task DAG built from bounded task contracts.

The graph is validated once, at construction. After that, `ready_task_ids` is a
pure function of the supplied state map, so the same inputs always produce the
same answer in the same order.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from legal_ai.orchestration.contracts import BoundedTaskContract
from legal_ai.orchestration.errors import TaskGraphError
from legal_ai.orchestration.types import TaskState

MAX_TASKS = 32
"""A bounded slice has a bounded DAG. A larger plan is a scope change."""


@dataclass(frozen=True, slots=True)
class TaskGraph:
    """A validated, bounded, acyclic set of bounded task contracts."""

    contracts: Mapping[str, BoundedTaskContract]
    topological_order: tuple[str, ...]

    def contract(self, task_id: str) -> BoundedTaskContract:
        try:
            return self.contracts[task_id]
        except KeyError as exc:
            raise TaskGraphError(f"unknown task {task_id!r}") from exc

    def dependencies_satisfied(self, task_id: str, states: Mapping[str, TaskState]) -> bool:
        """Return whether every dependency of `task_id` has completed."""

        contract = self.contract(task_id)
        for dependency in contract.depends_on:
            if states.get(dependency) is not TaskState.COMPLETED:
                return False
        return True

    def ready_task_ids(self, states: Mapping[str, TaskState]) -> tuple[str, ...]:
        """Return the pending tasks whose dependencies have all completed.

        The result follows the graph's topological order, so it is stable.
        """

        missing = set(self.contracts) - set(states)
        if missing:
            raise TaskGraphError(f"no state supplied for: {', '.join(sorted(missing))}")
        unknown = set(states) - set(self.contracts)
        if unknown:
            raise TaskGraphError(f"state supplied for unknown tasks: {', '.join(sorted(unknown))}")
        return tuple(
            task_id
            for task_id in self.topological_order
            if states[task_id] is TaskState.PENDING and self.dependencies_satisfied(task_id, states)
        )


def build_task_graph(contracts: Iterable[BoundedTaskContract]) -> TaskGraph:
    """Validate `contracts` into a bounded DAG, or fail closed."""

    ordered: Sequence[BoundedTaskContract] = tuple(contracts)
    if not ordered:
        raise TaskGraphError("a task graph must contain at least one contract")
    if len(ordered) > MAX_TASKS:
        raise TaskGraphError(f"a bounded task graph holds at most {MAX_TASKS} tasks")

    by_id: dict[str, BoundedTaskContract] = {}
    for contract in ordered:
        if contract.task_id in by_id:
            raise TaskGraphError(f"duplicate task id {contract.task_id!r}")
        by_id[contract.task_id] = contract

    for contract in ordered:
        for dependency in sorted(contract.depends_on):
            if dependency not in by_id:
                raise TaskGraphError(
                    f"task {contract.task_id!r} depends on unknown task {dependency!r}"
                )

    return TaskGraph(contracts=by_id, topological_order=_topological_order(by_id))


def _topological_order(by_id: Mapping[str, BoundedTaskContract]) -> tuple[str, ...]:
    """Kahn's algorithm over ids sorted lexicographically, so ties are stable."""

    remaining = {task_id: set(contract.depends_on) for task_id, contract in by_id.items()}
    order: list[str] = []

    while remaining:
        available = sorted(task_id for task_id, deps in remaining.items() if not deps)
        if not available:
            cycle = ", ".join(sorted(remaining))
            raise TaskGraphError(f"task graph contains a cycle among: {cycle}")
        for task_id in available:
            del remaining[task_id]
            order.append(task_id)
        for deps in remaining.values():
            deps.difference_update(available)

    return tuple(order)

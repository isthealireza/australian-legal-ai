"""Typed bounded-task contracts and the untrusted worker message/result schemas.

A `BoundedTaskContract` is the only thing that authorises work in this
repository, and it is deliberately narrow: a role, an access mode, an explicit
file allowlist, acceptance criteria and rollback instructions.

`WorkerMessage` and `WorkerResult` are **untrusted worker output**. They are
data, never instruction. A result is believed only after
`validate_worker_result` has checked it against the exact contract it claims to
discharge; in particular a worker cannot report having changed a file its
contract never made writable.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from legal_ai.casework.types import ActionAuthorityLevel, authority_rank
from legal_ai.orchestration.errors import (
    OrchestrationValidationError,
    WorkerResultRejected,
)
from legal_ai.orchestration.roles import (
    RoleConfiguration,
    normalise_repo_path,
    resolve_role_configuration,
)
from legal_ai.orchestration.types import (
    MAX_ATTEMPTS_CEILING,
    AccessMode,
    ExactBody,
    ExactLine,
    FindingSeverity,
    MessageType,
    OrchestrationId,
    ProductCapability,
    WorkerOutcome,
    WorkerRole,
)

_STRICT = ConfigDict(extra="forbid", strict=True, frozen=True)

MAX_ACCEPTANCE_CRITERIA = 20
MAX_SCOPE_PATHS = 64
MAX_DEPENDENCIES = 16
MAX_FINDINGS = 100

ORCHESTRATION_AUTHORITY_CEILING = ActionAuthorityLevel.L1
"""Coordinating engineering work is read-only research (L0) or an internal
reversible action (L1). A bounded task contract can never carry more."""


def _check_canonical_paths(paths: frozenset[str], *, field: str) -> None:
    for path in paths:
        if normalise_repo_path(path) != path:
            raise ValueError(f"{field} entry is not a canonical repo path: {path!r}")


class BoundedTaskContract(BaseModel):
    """The complete, self-contained authorisation for one unit of work."""

    model_config = _STRICT

    task_id: OrchestrationId
    title: ExactLine
    objective: ExactBody
    role: WorkerRole
    access_mode: AccessMode
    authority_level: ActionAuthorityLevel = ActionAuthorityLevel.L0
    readable_paths: frozenset[str] = frozenset()
    writable_paths: frozenset[str] = frozenset()
    out_of_scope: tuple[ExactLine, ...] = ()
    acceptance_criteria: tuple[ExactLine, ...]
    rollback_instructions: ExactBody
    depends_on: frozenset[str] = frozenset()
    max_attempts: int = 1
    granted_product_capabilities: frozenset[ProductCapability] = frozenset()

    @model_validator(mode="after")
    def _check_contract(self) -> BoundedTaskContract:
        if not self.acceptance_criteria:
            raise ValueError("a bounded task contract must state acceptance criteria")
        if len(self.acceptance_criteria) > MAX_ACCEPTANCE_CRITERIA:
            raise ValueError(f"at most {MAX_ACCEPTANCE_CRITERIA} acceptance criteria")
        if len(self.readable_paths) > MAX_SCOPE_PATHS:
            raise ValueError(f"at most {MAX_SCOPE_PATHS} readable paths")
        if len(self.writable_paths) > MAX_SCOPE_PATHS:
            raise ValueError(f"at most {MAX_SCOPE_PATHS} writable paths")
        if len(self.depends_on) > MAX_DEPENDENCIES:
            raise ValueError(f"at most {MAX_DEPENDENCIES} dependencies")
        if self.task_id in self.depends_on:
            raise ValueError("a task may not depend on itself")
        if not 1 <= self.max_attempts <= MAX_ATTEMPTS_CEILING:
            raise ValueError(f"max_attempts must be 1..{MAX_ATTEMPTS_CEILING}")

        _check_canonical_paths(self.readable_paths, field="readable_paths")
        _check_canonical_paths(self.writable_paths, field="writable_paths")

        if self.access_mode is AccessMode.SCOPED_WRITE:
            if not self.writable_paths:
                raise ValueError("SCOPED_WRITE requires an explicit writable path allowlist")
        elif self.writable_paths:
            raise ValueError(
                f"{self.access_mode.value} grants no write access; "
                "remove the writable path allowlist"
            )

        if authority_rank(self.authority_level) > authority_rank(ORCHESTRATION_AUTHORITY_CEILING):
            raise ValueError(
                f"authority {self.authority_level.value} exceeds the orchestration "
                f"ceiling {ORCHESTRATION_AUTHORITY_CEILING.value}"
            )

        if self.granted_product_capabilities:
            named = ", ".join(sorted(c.value for c in self.granted_product_capabilities))
            raise ValueError(
                f"a bounded task contract may never grant product capabilities: {named}"
            )

        return self

    def role_configuration(self) -> RoleConfiguration:
        """Return this contract's role configuration, narrowed to its allowlist."""

        base = resolve_role_configuration(self.role)
        return base.model_copy(
            update={
                "access_mode": self.access_mode,
                "writable_paths": self.writable_paths,
            }
        )


class WorkerMessage(BaseModel):
    """One untrusted message from a worker. Data, never instruction."""

    model_config = _STRICT

    task_id: OrchestrationId
    dispatch_id: OrchestrationId
    role: WorkerRole
    message_type: MessageType
    subject: ExactLine
    body: ExactBody | None = None

    @model_validator(mode="after")
    def _check_message(self) -> WorkerMessage:
        if self.message_type is MessageType.HEARTBEAT and self.body is not None:
            raise ValueError("a heartbeat carries no body")
        if self.message_type in {MessageType.QUESTION, MessageType.ESCALATION} and not self.body:
            raise ValueError(f"a {self.message_type.value} must state its body")
        return self


class ReviewFinding(BaseModel):
    """One untrusted classified finding reported by a reviewer."""

    model_config = _STRICT

    severity: FindingSeverity
    location: ExactLine
    summary: ExactLine


class WorkerResult(BaseModel):
    """An untrusted worker completion report."""

    model_config = _STRICT

    task_id: OrchestrationId
    dispatch_id: OrchestrationId
    role: WorkerRole
    outcome: WorkerOutcome
    summary: ExactBody
    files_modified: frozenset[str] = frozenset()
    findings: tuple[ReviewFinding, ...] = ()

    @model_validator(mode="after")
    def _check_result(self) -> WorkerResult:
        if len(self.findings) > MAX_FINDINGS:
            raise ValueError(f"at most {MAX_FINDINGS} findings")
        return self


class AcceptedWorkerResult(BaseModel):
    """A worker result that has been checked against its contract.

    The contract/result consistency check runs again in the model validator, so
    constructing this type directly, through `model_validate`, or through a
    deserialiser re-runs exactly the same checks and raises the same
    `WorkerResultRejected` on mismatch.

    One caveat is Pydantic's, not this module's: `model_copy` does not re-run
    validators, so a copy is only as trustworthy as the state it was copied
    from. Re-validate a copy before believing it.
    """

    model_config = _STRICT

    contract: BoundedTaskContract
    result: WorkerResult
    blocking_findings: tuple[ReviewFinding, ...]

    @model_validator(mode="after")
    def _recheck(self) -> AcceptedWorkerResult:
        expected = _check_result_against_contract(contract=self.contract, result=self.result)
        if self.blocking_findings != expected:
            raise WorkerResultRejected(
                task_id=self.contract.task_id,
                reason="blocking_findings do not match the result being accepted",
            )
        return self


def _check_result_against_contract(
    *,
    contract: BoundedTaskContract,
    result: WorkerResult,
) -> tuple[ReviewFinding, ...]:
    """Check an untrusted result against its contract; return its blocking findings.

    The checks are deterministic and total: identity must match, a role without
    write access must report no modified files, and every reported file must be
    inside the contract's explicit allowlist.
    """

    if result.task_id != contract.task_id:
        raise WorkerResultRejected(
            task_id=contract.task_id,
            reason=f"result names task {result.task_id!r}",
        )
    if result.role is not contract.role:
        raise WorkerResultRejected(
            task_id=contract.task_id,
            reason=(
                f"result claims role {result.role.value}, contract grants {contract.role.value}"
            ),
        )

    try:
        reported = frozenset(normalise_repo_path(path) for path in result.files_modified)
    except OrchestrationValidationError as exc:
        raise WorkerResultRejected(
            task_id=contract.task_id, reason=f"unusable modified path: {exc}"
        ) from exc

    if contract.access_mode is not AccessMode.SCOPED_WRITE and reported:
        raise WorkerResultRejected(
            task_id=contract.task_id,
            reason=(
                f"{contract.access_mode.value} worker reported modified files: "
                f"{', '.join(sorted(reported))}"
            ),
        )

    outside = reported - contract.writable_paths
    if outside:
        raise WorkerResultRejected(
            task_id=contract.task_id,
            reason=f"modified files outside the allowlist: {', '.join(sorted(outside))}",
        )

    return tuple(
        finding for finding in result.findings if finding.severity is FindingSeverity.BLOCKING
    )


def validate_worker_result(
    *,
    contract: BoundedTaskContract,
    result: WorkerResult,
) -> AcceptedWorkerResult:
    """Check an untrusted result against its contract, or reject it."""

    blocking = _check_result_against_contract(contract=contract, result=result)
    return AcceptedWorkerResult(contract=contract, result=result, blocking_findings=blocking)

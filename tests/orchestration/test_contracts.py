"""Bounded task contracts and validation of untrusted worker results."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from legal_ai.casework.types import ActionAuthorityLevel
from legal_ai.orchestration.contracts import (
    AcceptedWorkerResult,
    BoundedTaskContract,
    ReviewFinding,
    WorkerMessage,
    WorkerResult,
    validate_worker_result,
)
from legal_ai.orchestration.errors import WorkerResultRejected
from legal_ai.orchestration.types import (
    AccessMode,
    FindingSeverity,
    MessageType,
    ProductCapability,
    WorkerOutcome,
    WorkerRole,
)


def make_contract(**overrides: object) -> BoundedTaskContract:
    fields: dict[str, object] = {
        "task_id": "T1",
        "title": "Orchestration foundation",
        "objective": "Build the typed orchestration contracts.",
        "role": WorkerRole.IMPLEMENTER,
        "access_mode": AccessMode.SCOPED_WRITE,
        "writable_paths": frozenset({"src/legal_ai/orchestration/graph.py"}),
        "acceptance_criteria": ("The DAG rejects a cycle.",),
        "rollback_instructions": "git restore src/legal_ai/orchestration/graph.py",
    }
    fields.update(overrides)
    return BoundedTaskContract(**fields)  # type: ignore[arg-type]


def make_result(**overrides: object) -> WorkerResult:
    fields: dict[str, object] = {
        "task_id": "T1",
        "dispatch_id": "ctx_1",
        "role": WorkerRole.IMPLEMENTER,
        "outcome": WorkerOutcome.SUCCEEDED,
        "summary": "Built the graph module.",
    }
    fields.update(overrides)
    return WorkerResult(**fields)  # type: ignore[arg-type]


def test_contract_requires_acceptance_criteria() -> None:
    with pytest.raises(ValidationError):
        make_contract(acceptance_criteria=())


def test_contract_may_not_depend_on_itself() -> None:
    with pytest.raises(ValidationError):
        make_contract(depends_on=frozenset({"T1"}))


def test_review_only_contract_may_not_carry_writable_paths() -> None:
    with pytest.raises(ValidationError):
        make_contract(
            role=WorkerRole.REVIEWER,
            access_mode=AccessMode.REVIEW_ONLY,
        )


def make_review_contract() -> BoundedTaskContract:
    return make_contract(
        role=WorkerRole.REVIEWER,
        access_mode=AccessMode.REVIEW_ONLY,
        writable_paths=frozenset(),
    )


def test_scoped_write_needs_an_allowlist() -> None:
    with pytest.raises(ValidationError):
        make_contract(writable_paths=frozenset())


@pytest.mark.parametrize(
    "level",
    [
        ActionAuthorityLevel.L2,
        ActionAuthorityLevel.L4,
        ActionAuthorityLevel.L6,
    ],
)
def test_contract_cannot_exceed_the_orchestration_authority_ceiling(
    level: ActionAuthorityLevel,
) -> None:
    with pytest.raises(ValidationError):
        make_contract(authority_level=level)


@pytest.mark.parametrize("capability", list(ProductCapability))
def test_contract_can_never_grant_a_product_capability(
    capability: ProductCapability,
) -> None:
    with pytest.raises(ValidationError):
        make_contract(granted_product_capabilities=frozenset({capability}))


def test_contract_max_attempts_is_bounded() -> None:
    with pytest.raises(ValidationError):
        make_contract(max_attempts=4)
    with pytest.raises(ValidationError):
        make_contract(max_attempts=0)


def test_role_configuration_is_narrowed_to_the_contract_allowlist() -> None:
    configuration = make_contract().role_configuration()
    assert configuration.access_mode is AccessMode.SCOPED_WRITE
    assert configuration.writable_paths == frozenset({"src/legal_ai/orchestration/graph.py"})


def test_heartbeat_carries_no_body_and_a_question_must() -> None:
    WorkerMessage(
        task_id="T1",
        dispatch_id="ctx_1",
        role=WorkerRole.REVIEWER,
        message_type=MessageType.HEARTBEAT,
        subject="alive",
    )
    with pytest.raises(ValidationError):
        WorkerMessage(
            task_id="T1",
            dispatch_id="ctx_1",
            role=WorkerRole.REVIEWER,
            message_type=MessageType.HEARTBEAT,
            subject="alive",
            body="still working",
        )
    with pytest.raises(ValidationError):
        WorkerMessage(
            task_id="T1",
            dispatch_id="ctx_1",
            role=WorkerRole.REVIEWER,
            message_type=MessageType.QUESTION,
            subject="which base branch?",
        )


def test_accepted_result_reports_only_the_blocking_findings() -> None:
    contract = make_review_contract()
    result = make_result(
        role=WorkerRole.REVIEWER,
        findings=(
            ReviewFinding(
                severity=FindingSeverity.BLOCKING,
                location="src/legal_ai/orchestration/graph.py:1",
                summary="Cycle detection is unreachable.",
            ),
            ReviewFinding(
                severity=FindingSeverity.VALID_NON_BLOCKING,
                location="src/legal_ai/orchestration/roles.py:1",
                summary="Docstring could name the ADR.",
            ),
        ),
    )
    accepted = validate_worker_result(contract=contract, result=result)
    assert len(accepted.blocking_findings) == 1
    assert accepted.result is result


def test_result_for_another_task_is_rejected() -> None:
    with pytest.raises(WorkerResultRejected):
        validate_worker_result(contract=make_contract(), result=make_result(task_id="T9"))


def test_result_claiming_another_role_is_rejected() -> None:
    with pytest.raises(WorkerResultRejected):
        validate_worker_result(
            contract=make_contract(), result=make_result(role=WorkerRole.REVIEWER)
        )


def test_review_only_worker_reporting_a_modified_file_is_rejected() -> None:
    contract = make_review_contract()
    result = make_result(
        role=WorkerRole.REVIEWER,
        files_modified=frozenset({"src/legal_ai/orchestration/graph.py"}),
    )
    with pytest.raises(WorkerResultRejected) as excinfo:
        validate_worker_result(contract=contract, result=result)
    assert "reported modified files" in str(excinfo.value)


def test_file_outside_the_allowlist_is_rejected() -> None:
    result = make_result(files_modified=frozenset({"PROJECT_GOVERNANCE.md"}))
    with pytest.raises(WorkerResultRejected) as excinfo:
        validate_worker_result(contract=make_contract(), result=result)
    assert "outside the allowlist" in str(excinfo.value)


def test_traversal_in_a_reported_path_is_rejected_not_normalised_away() -> None:
    result = make_result(
        files_modified=frozenset({"src/legal_ai/orchestration/../../../PROJECT_GOVERNANCE.md"})
    )
    with pytest.raises(WorkerResultRejected) as excinfo:
        validate_worker_result(contract=make_contract(), result=result)
    assert "unusable modified path" in str(excinfo.value)


def test_allowlisted_file_is_accepted() -> None:
    result = make_result(files_modified=frozenset({"src/legal_ai/orchestration/graph.py"}))
    accepted = validate_worker_result(contract=make_contract(), result=result)
    assert accepted.blocking_findings == ()


def test_a_failed_outcome_still_validates_its_file_scope() -> None:
    result = make_result(
        outcome=WorkerOutcome.FAILED,
        files_modified=frozenset({"alembic.ini"}),
    )
    with pytest.raises(WorkerResultRejected):
        validate_worker_result(contract=make_contract(), result=result)


def test_accepted_result_cannot_be_forged_by_direct_construction() -> None:
    """The check re-runs in the validator, so there is no bypass constructor."""

    contract = make_review_contract()
    forged = make_result(
        role=WorkerRole.REVIEWER,
        files_modified=frozenset({"PROJECT_GOVERNANCE.md"}),
    )
    with pytest.raises(WorkerResultRejected):
        AcceptedWorkerResult(contract=contract, result=forged, blocking_findings=())


def test_accepted_result_cannot_be_forged_by_model_validate() -> None:
    contract = make_review_contract()
    forged = make_result(role=WorkerRole.IMPLEMENTER)
    with pytest.raises(WorkerResultRejected):
        AcceptedWorkerResult.model_validate(
            {"contract": contract, "result": forged, "blocking_findings": ()}
        )


def test_accepted_result_cannot_misreport_its_blocking_findings() -> None:
    contract = make_review_contract()
    result = make_result(
        role=WorkerRole.REVIEWER,
        findings=(
            ReviewFinding(
                severity=FindingSeverity.BLOCKING,
                location="src/legal_ai/orchestration/graph.py:1",
                summary="Cycle detection is unreachable.",
            ),
        ),
    )
    with pytest.raises(WorkerResultRejected) as excinfo:
        AcceptedWorkerResult(contract=contract, result=result, blocking_findings=())
    assert "do not match" in str(excinfo.value)


def test_model_copy_skips_validators_so_a_copy_is_rechecked_explicitly() -> None:
    """`model_copy` is Pydantic's documented escape hatch: it does not re-validate.

    An `AcceptedWorkerResult` therefore only proves the check ran for the state
    it was validated with. Re-validating a copy catches the tampering, which is
    what `validate_worker_result` callers get for free.
    """

    accepted = validate_worker_result(
        contract=make_review_contract(),
        result=make_result(role=WorkerRole.REVIEWER),
    )
    tampered = accepted.model_copy(
        update={"result": make_result(role=WorkerRole.REVIEWER, task_id="T9")}
    )
    assert tampered.result.task_id == "T9"

    with pytest.raises(WorkerResultRejected):
        AcceptedWorkerResult.model_validate(
            {
                "contract": tampered.contract,
                "result": tampered.result,
                "blocking_findings": tampered.blocking_findings,
            }
        )

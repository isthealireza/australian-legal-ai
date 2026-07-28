"""PostgreSQL integration tests for casework repository and service."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from legal_ai.casework.errors import (
    ActionAuthorityDenied,
    CaseworkValidationError,
    ClosedMatterMutationError,
    ConcurrencyConflictError,
    CrossMatterViolationError,
    NotFoundError,
    ReferenceAllocationError,
)
from legal_ai.casework.models import (
    AddDeadlineCommand,
    AddFactCommand,
    AddPartyCommand,
    AddTaskCommand,
    AssignRoleCommand,
    ConfirmDeadlineCommand,
    CreateMatterCommand,
    ReopenMatterCommand,
    TransitionMatterCommand,
    UpdateDeadlineDueCommand,
    UpdateFactStatusCommand,
    UpdateMatterCommand,
)
from legal_ai.casework.repository import CaseworkRepository
from legal_ai.casework.service import CaseworkService
from legal_ai.casework.types import (
    ActionAuthorityLevel,
    AuditEventType,
    CaseType,
    ConfirmationMethod,
    DeadlineConfidence,
    DeadlinePrecision,
    FactKind,
    FactStatus,
    Jurisdiction,
    MatterStatus,
    PartyEntityType,
    PartyRole,
    RiskLevel,
    VerificationMethod,
)

pytestmark = pytest.mark.integration


def _service(engine: Engine) -> CaseworkService:
    return CaseworkService(CaseworkRepository(engine))


def _create_cmd(**overrides: object) -> CreateMatterCommand:
    data: dict[str, object] = {
        "title": "Integration matter",
        "jurisdiction": Jurisdiction.AU_WA,
        "case_type": CaseType.UNASSIGNED,
        "risk_level": RiskLevel.R1,
        "action_authority_ceiling": ActionAuthorityLevel.L1,
        "actor": "integrator",
        "source_channel": "integration",
    }
    data.update(overrides)
    return CreateMatterCommand.model_validate(data)


def test_create_matter_uuid_consistency_and_reference_format(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)
    matter = service.create_matter(_create_cmd())
    loaded = service.get_matter(matter.matter_id, actor="integrator", source_channel="integration")
    assert loaded.matter_id == matter.matter_id
    assert isinstance(matter.matter_id, UUID)
    assert matter.reference.startswith("MAT-")
    assert len(matter.reference) == 16
    assert matter.reference[4:].isdigit()
    events = service.list_audit_events(matter.matter_id)
    assert events[0].event_type is AuditEventType.MATTER_CREATED
    assert events[0].entity_id == matter.matter_id
    assert events[0].matter_id == matter.matter_id


def test_concurrent_creates_unique_references(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)

    def _create(_: int) -> str:
        return service.create_matter(_create_cmd(title=f"concurrent-{uuid4().hex}")).reference

    with ThreadPoolExecutor(max_workers=8) as pool:
        refs = list(pool.map(_create, range(16)))
    assert len(refs) == len(set(refs))


def test_rollback_leaves_sequence_gap_without_missing_matter(migrated_engine: Engine) -> None:
    repo = CaseworkRepository(migrated_engine)
    with repo.transaction() as connection:
        first_ref = repo.allocate_reference(connection)
        first_value = int(first_ref.removeprefix("MAT-"))

    with pytest.raises(CaseworkValidationError):
        with repo.transaction() as connection:
            gap_ref = repo.allocate_reference(connection)
            assert int(gap_ref.removeprefix("MAT-")) == first_value + 1
            # Force rollback after consuming nextval.
            raise CaseworkValidationError("forced rollback")

    service = _service(migrated_engine)
    matter = service.create_matter(_create_cmd(title="after-gap"))
    created_value = int(matter.reference.removeprefix("MAT-"))
    assert created_value >= first_value + 2
    with migrated_engine.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM casework_matters")).scalar_one()
    assert int(count) == 1


def test_unexpected_reference_unique_violation_raises_reference_allocation_error(
    migrated_engine: Engine,
) -> None:
    with migrated_engine.begin() as connection:
        next_val = int(
            connection.execute(text("SELECT nextval('casework_matter_reference_seq')")).scalar_one()
        )
        reference = f"MAT-{next_val:012d}"
        connection.execute(
            text(
                "INSERT INTO casework_matters ("
                "matter_id, reference, title, status, jurisdiction, case_type, "
                "risk_level, action_authority_ceiling, created_by, updated_by"
                ") VALUES ("
                ":mid, :reference, 'collision', 'INTAKE_INCOMPLETE', 'AU-WA', "
                "'UNASSIGNED', 'R0', 'L1', 'seed', 'seed')"
            ),
            {"mid": uuid4(), "reference": reference},
        )
        # Next nextval returns the same value, colliding with the seeded reference.
        connection.execute(
            text("SELECT setval('casework_matter_reference_seq', :value, false)"),
            {"value": next_val},
        )

    service = _service(migrated_engine)
    with pytest.raises(ReferenceAllocationError):
        service.create_matter(_create_cmd(title="should-collide"))


def test_concurrency_conflict(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)
    matter = service.create_matter(_create_cmd())
    service.update_matter(
        UpdateMatterCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "row_version": matter.row_version,
                "title": "updated-once",
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    with pytest.raises(ConcurrencyConflictError):
        service.update_matter(
            UpdateMatterCommand.model_validate(
                {
                    "matter_id": matter.matter_id,
                    "row_version": matter.row_version,
                    "title": "stale",
                    "actor": "integrator",
                    "source_channel": "integration",
                }
            )
        )


def test_closed_mutation_rejection_and_reopen(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)
    matter = service.create_matter(_create_cmd())
    party = service.add_party(
        AddPartyCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "entity_type": PartyEntityType.NATURAL_PERSON,
                "display_name": "Subject",
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    service.assign_role(
        AssignRoleCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "party_id": party.party_id,
                "role": PartyRole.PRIMARY_SUBJECT,
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    matter = service.get_matter(matter.matter_id, actor="integrator", source_channel="integration")
    matter = service.transition_matter(
        TransitionMatterCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "row_version": matter.row_version,
                "target_status": MatterStatus.INTAKE_COMPLETE,
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    matter = service.transition_matter(
        TransitionMatterCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "row_version": matter.row_version,
                "target_status": MatterStatus.ACTIVE,
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    matter = service.transition_matter(
        TransitionMatterCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "row_version": matter.row_version,
                "target_status": MatterStatus.RESOLVED,
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    matter = service.transition_matter(
        TransitionMatterCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "row_version": matter.row_version,
                "target_status": MatterStatus.CLOSED,
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    with pytest.raises(ClosedMatterMutationError):
        service.add_fact(
            AddFactCommand.model_validate(
                {
                    "matter_id": matter.matter_id,
                    "kind": FactKind.OBSERVED,
                    "statement": "blocked",
                    "actor": "integrator",
                    "source_channel": "integration",
                }
            )
        )
    reopened = service.reopen_matter(
        ReopenMatterCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "row_version": matter.row_version,
                "target_status": MatterStatus.ACTIVE,
                "actor": "integrator",
                "source_channel": "integration",
                "reason": "need to continue work",
            }
        )
    )
    assert reopened.status is MatterStatus.ACTIVE
    assert reopened.closed_at is None
    events = service.list_audit_events(matter.matter_id)
    assert any(event.event_type is AuditEventType.MATTER_REOPENED for event in events)


def test_primary_subject_required_for_intake_complete(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)
    matter = service.create_matter(_create_cmd())
    party = service.add_party(
        AddPartyCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "entity_type": PartyEntityType.NATURAL_PERSON,
                "display_name": "Client only",
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    service.assign_role(
        AssignRoleCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "party_id": party.party_id,
                "role": PartyRole.CLIENT,
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    with pytest.raises(CaseworkValidationError, match="PRIMARY_SUBJECT"):
        service.transition_matter(
            TransitionMatterCommand.model_validate(
                {
                    "matter_id": matter.matter_id,
                    "row_version": matter.row_version,
                    "target_status": MatterStatus.INTAKE_COMPLETE,
                    "actor": "integrator",
                    "source_channel": "integration",
                }
            )
        )


def test_cross_matter_party_and_task_attacks(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)
    matter_a = service.create_matter(_create_cmd(title="A"))
    matter_b = service.create_matter(_create_cmd(title="B"))
    party_a = service.add_party(
        AddPartyCommand.model_validate(
            {
                "matter_id": matter_a.matter_id,
                "entity_type": PartyEntityType.ORGANISATION,
                "display_name": "Org A",
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    with pytest.raises(NotFoundError):
        service.assign_role(
            AssignRoleCommand.model_validate(
                {
                    "matter_id": matter_b.matter_id,
                    "party_id": party_a.party_id,
                    "role": PartyRole.OTHER,
                    "actor": "integrator",
                    "source_channel": "integration",
                }
            )
        )
    deadline_a = service.add_deadline(
        AddDeadlineCommand.model_validate(
            {
                "matter_id": matter_a.matter_id,
                "source_description": "listing",
                "jurisdiction": Jurisdiction.AU_WA,
                "confidence": DeadlineConfidence.MEDIUM,
                "responsible_actor": "integrator",
                "timezone": "Australia/Perth",
                "precision": DeadlinePrecision.DATE,
                "due_date": date(2026, 9, 1),
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    with pytest.raises((NotFoundError, CrossMatterViolationError)):
        service.add_task(
            AddTaskCommand.model_validate(
                {
                    "matter_id": matter_b.matter_id,
                    "title": "cross link",
                    "deadline_id": deadline_a.deadline_id,
                    "actor": "integrator",
                    "source_channel": "integration",
                }
            )
        )


def test_audit_update_and_delete_via_raw_sql_fail(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)
    matter = service.create_matter(_create_cmd())
    with migrated_engine.begin() as connection:
        event_id = connection.execute(
            text("SELECT event_id FROM casework_audit_events WHERE matter_id = :mid LIMIT 1"),
            {"mid": matter.matter_id},
        ).scalar_one()
        with pytest.raises(DBAPIError, match="immutable"):
            connection.execute(
                text("UPDATE casework_audit_events SET actor = 'tamper' WHERE event_id = :eid"),
                {"eid": event_id},
            )
    with migrated_engine.begin() as connection:
        event_id = connection.execute(
            text("SELECT event_id FROM casework_audit_events WHERE matter_id = :mid LIMIT 1"),
            {"mid": matter.matter_id},
        ).scalar_one()
        with pytest.raises(DBAPIError, match="immutable"):
            connection.execute(
                text("DELETE FROM casework_audit_events WHERE event_id = :eid"),
                {"eid": event_id},
            )


def test_audit_failure_rolls_back_domain_writes(migrated_engine: Engine) -> None:
    repo = CaseworkRepository(migrated_engine)
    matter_id = uuid4()
    with pytest.raises(IntegrityError):
        with repo.transaction() as connection:
            reference = repo.allocate_reference(connection)
            repo.insert_matter(
                connection,
                matter_id=matter_id,
                reference=reference,
                title="audit-fail",
                summary=None,
                jurisdiction=Jurisdiction.AU_WA,
                case_type=CaseType.UNASSIGNED,
                risk_level=RiskLevel.R0,
                action_authority_ceiling=ActionAuthorityLevel.L1,
                actor="integrator",
            )
            # Violate audit metadata size CHECK to force rollback of the whole txn.
            connection.execute(
                text(
                    "INSERT INTO casework_audit_events ("
                    "event_id, matter_id, actor, event_type, entity_type, "
                    "source_channel, metadata"
                    ") VALUES ("
                    ":eid, :mid, 'integrator', 'MATTER_CREATED', 'matter', "
                    "'integration', CAST(:meta AS jsonb)"
                    ")"
                ),
                {
                    "eid": uuid4(),
                    "mid": matter_id,
                    "meta": '{"command_type":"' + ("x" * 5000) + '"}',
                },
            )
    with migrated_engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM casework_matters WHERE matter_id = :mid"),
            {"mid": matter_id},
        ).scalar_one()
    assert int(count) == 0


def test_denial_paths(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)
    matter = service.create_matter(_create_cmd(action_authority_ceiling=ActionAuthorityLevel.L0))
    with pytest.raises(ActionAuthorityDenied):
        service.add_fact(
            AddFactCommand.model_validate(
                {
                    "matter_id": matter.matter_id,
                    "kind": FactKind.OBSERVED,
                    "statement": "denied write",
                    "actor": "integrator",
                    "source_channel": "integration",
                }
            )
        )
    events = service.list_audit_events(matter.matter_id)
    denied = [event for event in events if event.event_type is AuditEventType.ACTION_DENIED]
    assert len(denied) == 1
    assert denied[0].metadata["required_level"] == "L1"
    assert "statement" not in denied[0].metadata
    with migrated_engine.connect() as connection:
        facts = connection.execute(
            text("SELECT count(*) FROM casework_fact_items WHERE matter_id = :mid"),
            {"mid": matter.matter_id},
        ).scalar_one()
    assert int(facts) == 0


def test_fact_verification_constraints_at_db(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)
    matter = service.create_matter(_create_cmd())
    fact = service.add_fact(
        AddFactCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "kind": FactKind.OBSERVED,
                "statement": "observed fact",
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    verified = service.update_fact_status(
        UpdateFactStatusCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "fact_id": fact.fact_id,
                "status": FactStatus.VERIFIED,
                "actor": "integrator",
                "source_channel": "integration",
                "verified_by": "integrator",
                "verified_at": datetime(2026, 7, 28, tzinfo=UTC),
                "verification_method": VerificationMethod.OPERATOR_ATTESTATION,
                "verification_note": "operator attested",
            }
        )
    )
    assert verified.status is FactStatus.VERIFIED
    assert verified.verification_source_ref is None

    with migrated_engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "UPDATE casework_fact_items SET status = 'VERIFIED', "
                    "verified_by = NULL WHERE fact_id = :fid"
                ),
                {"fid": fact.fact_id},
            )


def test_deadline_confirmation_cleared_on_due_edit(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)
    matter = service.create_matter(_create_cmd())
    deadline = service.add_deadline(
        AddDeadlineCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "source_description": "external notice",
                "jurisdiction": Jurisdiction.AU_WA,
                "confidence": DeadlineConfidence.HIGH,
                "responsible_actor": "integrator",
                "timezone": "Australia/Perth",
                "precision": DeadlinePrecision.DATE,
                "due_date": date(2026, 10, 1),
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    confirmed = service.confirm_deadline(
        ConfirmDeadlineCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "deadline_id": deadline.deadline_id,
                "confirmed_by": "integrator",
                "confirmation_method": ConfirmationMethod.OPERATOR_ATTESTATION,
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    assert confirmed.confirmed_by == "integrator"
    updated = service.update_deadline_due(
        UpdateDeadlineDueCommand.model_validate(
            {
                "matter_id": matter.matter_id,
                "deadline_id": deadline.deadline_id,
                "timezone": "Australia/Perth",
                "precision": DeadlinePrecision.DATE,
                "due_date": date(2026, 10, 15),
                "actor": "integrator",
                "source_channel": "integration",
            }
        )
    )
    assert updated.confirmed_by is None
    assert updated.confirmed_at is None
    assert updated.confirmation_method is None
    events = service.list_audit_events(matter.matter_id)
    types = {event.event_type for event in events}
    assert AuditEventType.DEADLINE_DUE_VALUE_CHANGED in types
    assert AuditEventType.DEADLINE_CONFIRMATION_CLEARED in types


def test_repository_rejects_insert_without_matter_id_conceptually(
    migrated_engine: Engine,
) -> None:
    # Application UUID presence is enforced before insert; repository maps missing parents.
    repo = CaseworkRepository(migrated_engine)
    with pytest.raises((NotFoundError, CrossMatterViolationError, CaseworkValidationError)):
        with repo.transaction() as connection:
            repo.insert_party(
                connection,
                party_id=uuid4(),
                matter_id=uuid4(),
                entity_type=PartyEntityType.NATURAL_PERSON,
                display_name="orphan",
            )

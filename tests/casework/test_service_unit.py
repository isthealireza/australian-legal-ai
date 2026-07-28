"""Unit tests for CaseworkService validation, authority, and denial paths."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from legal_ai.casework.errors import (
    ActionAuthorityDenied,
    AuditWriteFailed,
    CaseworkValidationError,
    ClosedMatterMutationError,
    NotFoundError,
)
from legal_ai.casework.models import (
    AddFactCommand,
    AuditEventRecord,
    CreateMatterCommand,
    FactItemRecord,
    MatterRecord,
    TransitionMatterCommand,
    UpdateFactStatusCommand,
)
from legal_ai.casework.service import CaseworkService
from legal_ai.casework.types import (
    ActionAuthorityLevel,
    AuditEventType,
    CaseType,
    FactKind,
    FactStatus,
    Jurisdiction,
    MatterStatus,
    RiskLevel,
    VerificationMethod,
)


class _FakeConnection:
    pass


class FakeCaseworkRepository:
    """In-memory repository stand-in for DB-free service unit tests."""

    def __init__(self) -> None:
        self.matters: dict[UUID, MatterRecord] = {}
        self.facts: dict[tuple[UUID, UUID], FactItemRecord] = {}
        self.audit_events: list[AuditEventRecord] = []
        self._seq = 0
        self.fail_audit = False
        self.fail_denial_audit = False
        self.domain_writes: list[str] = []

    @contextmanager
    def transaction(self) -> Iterator[_FakeConnection]:
        yield _FakeConnection()

    def allocate_reference(self, connection: _FakeConnection) -> str:
        del connection
        self._seq += 1
        return f"MAT-{self._seq:012d}"

    def insert_matter(self, connection: _FakeConnection, **kwargs: Any) -> MatterRecord:
        del connection
        self.domain_writes.append("insert_matter")
        now = datetime.now(UTC)
        matter = MatterRecord(
            matter_id=kwargs["matter_id"],
            reference=kwargs["reference"],
            title=kwargs["title"],
            summary=kwargs["summary"],
            status=MatterStatus.INTAKE_INCOMPLETE,
            jurisdiction=kwargs["jurisdiction"],
            case_type=kwargs["case_type"],
            risk_level=kwargs["risk_level"],
            action_authority_ceiling=kwargs["action_authority_ceiling"],
            row_version=1,
            created_by=kwargs["actor"],
            updated_by=kwargs["actor"],
            created_at=now,
            updated_at=now,
            closed_at=None,
            assigned_playbook_version_id=None,
            playbook_assigned_at=None,
            playbook_assigned_by=None,
        )
        self.matters[matter.matter_id] = matter
        return matter

    def require_matter(self, connection: _FakeConnection, matter_id: UUID) -> MatterRecord:
        del connection
        try:
            return self.matters[matter_id]
        except KeyError as exc:
            raise NotFoundError(f"matter not found: {matter_id}") from exc

    def get_matter(self, connection: _FakeConnection, matter_id: UUID) -> MatterRecord | None:
        del connection
        return self.matters.get(matter_id)

    def has_primary_subject(self, connection: _FakeConnection, matter_id: UUID) -> bool:
        del connection, matter_id
        return False

    def update_matter_optimistic(
        self,
        connection: _FakeConnection,
        *,
        matter_id: UUID,
        expected_row_version: int,
        values: dict[str, Any],
    ) -> MatterRecord:
        del connection
        self.domain_writes.append("update_matter")
        matter = self.matters[matter_id]
        updated = MatterRecord(
            matter_id=matter.matter_id,
            reference=matter.reference,
            title=str(values.get("title", matter.title)),
            summary=matter.summary,
            status=MatterStatus(str(values.get("status", matter.status.value))),
            jurisdiction=matter.jurisdiction,
            case_type=(
                CaseType(str(values["case_type"])) if "case_type" in values else matter.case_type
            ),
            risk_level=matter.risk_level,
            action_authority_ceiling=matter.action_authority_ceiling,
            row_version=expected_row_version + 1,
            created_by=matter.created_by,
            updated_by=str(values.get("updated_by", matter.updated_by)),
            created_at=matter.created_at,
            updated_at=datetime.now(UTC),
            closed_at=cast("datetime | None", values.get("closed_at", matter.closed_at)),
            assigned_playbook_version_id=cast(
                "UUID | None",
                values.get("assigned_playbook_version_id", matter.assigned_playbook_version_id),
            ),
            playbook_assigned_at=cast(
                "datetime | None",
                values.get("playbook_assigned_at", matter.playbook_assigned_at),
            ),
            playbook_assigned_by=cast(
                "str | None",
                values.get("playbook_assigned_by", matter.playbook_assigned_by),
            ),
        )
        self.matters[matter_id] = updated
        return updated

    def insert_fact(self, connection: _FakeConnection, **kwargs: Any) -> FactItemRecord:
        del connection
        self.domain_writes.append("insert_fact")
        fact = FactItemRecord(
            fact_id=kwargs["fact_id"],
            matter_id=kwargs["matter_id"],
            kind=kwargs["kind"],
            status=kwargs["status"],
            statement=kwargs["statement"],
            source_ref=kwargs["source_ref"],
            source_channel=kwargs["source_channel"],
            verified_by=None,
            verified_at=None,
            verification_method=None,
            verification_source_ref=None,
            verification_note=None,
            created_at=datetime.now(UTC),
        )
        self.facts[(fact.matter_id, fact.fact_id)] = fact
        return fact

    def require_fact(
        self, connection: _FakeConnection, *, matter_id: UUID, fact_id: UUID
    ) -> FactItemRecord:
        del connection
        return self.facts[(matter_id, fact_id)]

    def update_fact_status(self, connection: _FakeConnection, **kwargs: Any) -> FactItemRecord:
        del connection
        self.domain_writes.append("update_fact")
        key = (kwargs["matter_id"], kwargs["fact_id"])
        existing = self.facts[key]
        updated = FactItemRecord(
            fact_id=existing.fact_id,
            matter_id=existing.matter_id,
            kind=existing.kind,
            status=kwargs["status"],
            statement=existing.statement,
            source_ref=existing.source_ref,
            source_channel=existing.source_channel,
            verified_by=kwargs["verified_by"],
            verified_at=kwargs["verified_at"],
            verification_method=kwargs["verification_method"],
            verification_source_ref=kwargs["verification_source_ref"],
            verification_note=kwargs["verification_note"],
            created_at=existing.created_at,
        )
        self.facts[key] = updated
        return updated

    def append_audit_event(self, connection: _FakeConnection, **kwargs: Any) -> AuditEventRecord:
        del connection
        event_type = kwargs["event_type"]
        if event_type is AuditEventType.ACTION_DENIED and self.fail_denial_audit:
            raise RuntimeError("denial audit sink unavailable")
        if event_type is not AuditEventType.ACTION_DENIED and self.fail_audit:
            raise RuntimeError("audit sink unavailable")
        event = AuditEventRecord(
            event_id=kwargs["event_id"],
            matter_id=kwargs["matter_id"],
            actor=kwargs["actor"],
            event_type=event_type,
            entity_type=kwargs["entity_type"],
            entity_id=kwargs["entity_id"],
            occurred_at=datetime.now(UTC),
            correlation_id=kwargs["correlation_id"],
            reason=kwargs["reason"],
            source_channel=kwargs["source_channel"],
            metadata=dict(kwargs.get("metadata") or {}),
        )
        self.audit_events.append(event)
        return event

    def list_audit_events(
        self, connection: _FakeConnection, matter_id: UUID
    ) -> list[AuditEventRecord]:
        del connection
        return [event for event in self.audit_events if event.matter_id == matter_id]


def _service(
    repo: FakeCaseworkRepository | None = None,
) -> tuple[CaseworkService, FakeCaseworkRepository]:
    fake = repo or FakeCaseworkRepository()
    return CaseworkService(fake), fake  # type: ignore[arg-type]


def _seed_matter(
    fake: FakeCaseworkRepository,
    *,
    ceiling: ActionAuthorityLevel = ActionAuthorityLevel.L1,
    status: MatterStatus = MatterStatus.INTAKE_INCOMPLETE,
) -> MatterRecord:
    matter_id = uuid4()
    now = datetime.now(UTC)
    matter = MatterRecord(
        matter_id=matter_id,
        reference="MAT-000000000001",
        title="Seeded",
        summary=None,
        status=status,
        jurisdiction=Jurisdiction.AU_WA,
        case_type=CaseType.UNASSIGNED,
        risk_level=RiskLevel.R0,
        action_authority_ceiling=ceiling,
        row_version=1,
        created_by="seed",
        updated_by="seed",
        created_at=now,
        updated_at=now,
        closed_at=datetime.now(UTC) if status is MatterStatus.CLOSED else None,
        assigned_playbook_version_id=None,
        playbook_assigned_at=None,
        playbook_assigned_by=None,
    )
    fake.matters[matter_id] = matter
    return matter


def test_create_matter_returns_handler_generated_uuid_and_reference() -> None:
    service, fake = _service()
    matter = service.create_matter(
        CreateMatterCommand.model_validate(
            {
                "title": "Created",
                "jurisdiction": Jurisdiction.AU_WA,
                "action_authority_ceiling": ActionAuthorityLevel.L1,
                "actor": "op",
                "source_channel": "unit",
            }
        )
    )
    assert matter.matter_id in fake.matters
    assert matter.reference == "MAT-000000000001"
    assert matter.status is MatterStatus.INTAKE_INCOMPLETE
    assert fake.audit_events[0].entity_id == matter.matter_id
    assert fake.audit_events[0].event_type is AuditEventType.MATTER_CREATED


def test_denial_records_action_denied_without_domain_mutation() -> None:
    service, fake = _service()
    matter = _seed_matter(fake, ceiling=ActionAuthorityLevel.L0)
    writes_before = list(fake.domain_writes)
    with pytest.raises(ActionAuthorityDenied):
        service.add_fact(
            AddFactCommand.model_validate(
                {
                    "matter_id": matter.matter_id,
                    "kind": FactKind.OBSERVED,
                    "statement": "should deny",
                    "actor": "op",
                    "source_channel": "unit",
                }
            )
        )
    assert fake.domain_writes == writes_before
    denied = [
        event for event in fake.audit_events if event.event_type is AuditEventType.ACTION_DENIED
    ]
    assert len(denied) == 1
    assert denied[0].metadata["command_type"] == "AddFact"
    assert "statement" not in denied[0].metadata
    assert "payload" not in denied[0].metadata


def test_denial_audit_failure_raises_audit_write_failed_with_denial_cause() -> None:
    service, fake = _service()
    fake.fail_denial_audit = True
    matter = _seed_matter(fake, ceiling=ActionAuthorityLevel.L0)
    with pytest.raises(AuditWriteFailed) as exc_info:
        service.add_fact(
            AddFactCommand.model_validate(
                {
                    "matter_id": matter.matter_id,
                    "kind": FactKind.OBSERVED,
                    "statement": "should deny",
                    "actor": "op",
                    "source_channel": "unit",
                }
            )
        )
    assert isinstance(exc_info.value.__cause__, ActionAuthorityDenied)


def test_closed_matter_rejects_mutation() -> None:
    service, fake = _service()
    matter = _seed_matter(fake, status=MatterStatus.CLOSED)
    with pytest.raises(ClosedMatterMutationError):
        service.add_fact(
            AddFactCommand.model_validate(
                {
                    "matter_id": matter.matter_id,
                    "kind": FactKind.OBSERVED,
                    "statement": "closed",
                    "actor": "op",
                    "source_channel": "unit",
                }
            )
        )


def test_intake_complete_requires_primary_subject() -> None:
    service, fake = _service()
    matter = _seed_matter(fake)
    with pytest.raises(CaseworkValidationError, match="PRIMARY_SUBJECT"):
        service.transition_matter(
            TransitionMatterCommand.model_validate(
                {
                    "matter_id": matter.matter_id,
                    "row_version": 1,
                    "target_status": MatterStatus.INTAKE_COMPLETE,
                    "actor": "op",
                    "source_channel": "unit",
                }
            )
        )


def test_assumption_cannot_become_verified() -> None:
    service, fake = _service()
    matter = _seed_matter(fake)
    fact_id = uuid4()
    fake.facts[(matter.matter_id, fact_id)] = FactItemRecord(
        fact_id=fact_id,
        matter_id=matter.matter_id,
        kind=FactKind.ASSUMPTION,
        status=FactStatus.ASSERTED,
        statement="assumed",
        source_ref=None,
        source_channel="unit",
        verified_by=None,
        verified_at=None,
        verification_method=None,
        verification_source_ref=None,
        verification_note=None,
        created_at=datetime.now(UTC),
    )
    with pytest.raises(CaseworkValidationError, match="ASSUMPTION"):
        service.update_fact_status(
            UpdateFactStatusCommand.model_validate(
                {
                    "matter_id": matter.matter_id,
                    "fact_id": fact_id,
                    "status": FactStatus.VERIFIED,
                    "actor": "op",
                    "source_channel": "unit",
                    "verified_by": "op",
                    "verified_at": datetime(2026, 7, 28, tzinfo=UTC),
                    "verification_method": VerificationMethod.OPERATOR_ATTESTATION,
                    "verification_note": "nope",
                }
            )
        )


def test_audit_failure_on_create_raises_audit_write_failed() -> None:
    service, fake = _service()
    fake.fail_audit = True
    with pytest.raises(AuditWriteFailed):
        service.create_matter(
            CreateMatterCommand.model_validate(
                {
                    "title": "Created",
                    "jurisdiction": Jurisdiction.AU_WA,
                    "action_authority_ceiling": ActionAuthorityLevel.L1,
                    "actor": "op",
                    "source_channel": "unit",
                }
            )
        )

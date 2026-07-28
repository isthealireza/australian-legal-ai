"""SQLAlchemy Core repository for Phase 1 Generic Casework Core."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Connection, Engine, RowMapping, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from legal_ai.casework.errors import (
    CaseworkValidationError,
    ConcurrencyConflictError,
    CrossMatterViolationError,
    NotFoundError,
    ReferenceAllocationError,
)
from legal_ai.casework.models import (
    AuditEventRecord,
    DeadlineRecord,
    FactItemRecord,
    IssueRecord,
    MatterRecord,
    PartyRecord,
    PartyRoleRecord,
    TaskRecord,
    validate_audit_metadata,
)
from legal_ai.casework.types import (
    ActionAuthorityLevel,
    AuditEventType,
    CaseType,
    ConfirmationMethod,
    DeadlineConfidence,
    DeadlinePrecision,
    DeadlineStatus,
    FactKind,
    FactStatus,
    IssueStatus,
    IssueType,
    Jurisdiction,
    MatterStatus,
    PartyEntityType,
    PartyRole,
    RiskLevel,
    TaskStatus,
    VerificationMethod,
)
from legal_ai.db import (
    casework_audit_events,
    casework_deadlines,
    casework_fact_items,
    casework_issues,
    casework_matters,
    casework_parties,
    casework_party_roles,
    casework_tasks,
)

_REFERENCE_SEQUENCE = "casework_matter_reference_seq"


class CaseworkRepository:
    """Matter-scoped persistence using explicit SQLAlchemy Core transactions."""

    def __init__(self, bind: Engine | Connection) -> None:
        self._bind = bind

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        if isinstance(self._bind, Engine):
            with self._bind.begin() as connection:
                yield connection
            return

        if self._bind.in_transaction():
            with self._bind.begin_nested():
                yield self._bind
            return

        with self._bind.begin():
            yield self._bind

    def allocate_reference(self, connection: Connection) -> str:
        value = connection.execute(text(f"SELECT nextval('{_REFERENCE_SEQUENCE}')")).scalar_one()
        return f"MAT-{int(value):012d}"

    def insert_matter(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        reference: str,
        title: str,
        summary: str | None,
        jurisdiction: Jurisdiction,
        case_type: CaseType,
        risk_level: RiskLevel,
        action_authority_ceiling: ActionAuthorityLevel,
        actor: str,
    ) -> MatterRecord:
        if matter_id is None:  # pragma: no cover - defensive
            raise CaseworkValidationError("matter_id is required before insert")
        try:
            connection.execute(
                insert(casework_matters).values(
                    matter_id=matter_id,
                    reference=reference,
                    title=title,
                    summary=summary,
                    status=MatterStatus.INTAKE_INCOMPLETE.value,
                    jurisdiction=jurisdiction.value,
                    case_type=case_type.value,
                    risk_level=risk_level.value,
                    action_authority_ceiling=action_authority_ceiling.value,
                    created_by=actor,
                    updated_by=actor,
                )
            )
        except IntegrityError as exc:
            self._map_integrity_error(exc, reference_conflict=True)
        return self.require_matter(connection, matter_id)

    def get_matter(
        self,
        connection: Connection,
        matter_id: UUID,
    ) -> MatterRecord | None:
        row = (
            connection.execute(
                select(casework_matters).where(casework_matters.c.matter_id == matter_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return self._matter_record(row)

    def require_matter(self, connection: Connection, matter_id: UUID) -> MatterRecord:
        matter = self.get_matter(connection, matter_id)
        if matter is None:
            raise NotFoundError(f"matter not found: {matter_id}")
        return matter

    def update_matter_optimistic(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        expected_row_version: int,
        values: Mapping[str, Any],
    ) -> MatterRecord:
        payload = dict(values)
        payload["row_version"] = expected_row_version + 1
        result = connection.execute(
            update(casework_matters)
            .where(
                casework_matters.c.matter_id == matter_id,
                casework_matters.c.row_version == expected_row_version,
            )
            .values(**payload)
        )
        if result.rowcount != 1:
            raise ConcurrencyConflictError(
                f"matter {matter_id} row_version conflict at {expected_row_version}"
            )
        return self.require_matter(connection, matter_id)

    def lock_matter(self, connection: Connection, matter_id: UUID) -> MatterRecord:
        """Lock the matter row (SELECT FOR UPDATE) and return the current record."""

        row = (
            connection.execute(
                select(casework_matters)
                .where(casework_matters.c.matter_id == matter_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"matter not found: {matter_id}")
        return self._matter_record(row)

    def update_matter_pin(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        expected_row_version: int,
        assigned_playbook_version_id: UUID | None,
        playbook_assigned_at: datetime | None,
        playbook_assigned_by: str | None,
        updated_by: str,
        case_type: CaseType | None = None,
        status: MatterStatus | None = None,
    ) -> MatterRecord:
        """Update playbook pin metadata with optimistic concurrency."""

        values: dict[str, Any] = {
            "assigned_playbook_version_id": assigned_playbook_version_id,
            "playbook_assigned_at": playbook_assigned_at,
            "playbook_assigned_by": playbook_assigned_by,
            "updated_by": updated_by,
        }
        if case_type is not None:
            values["case_type"] = case_type.value
        if status is not None:
            values["status"] = status.value
        return self.update_matter_optimistic(
            connection,
            matter_id=matter_id,
            expected_row_version=expected_row_version,
            values=values,
        )

    def insert_party(
        self,
        connection: Connection,
        *,
        party_id: UUID,
        matter_id: UUID,
        entity_type: PartyEntityType,
        display_name: str,
    ) -> PartyRecord:
        try:
            connection.execute(
                insert(casework_parties).values(
                    party_id=party_id,
                    matter_id=matter_id,
                    entity_type=entity_type.value,
                    display_name=display_name,
                )
            )
        except IntegrityError as exc:
            self._map_integrity_error(exc)
        return self.require_party(connection, matter_id=matter_id, party_id=party_id)

    def get_party(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        party_id: UUID,
    ) -> PartyRecord | None:
        row = (
            connection.execute(
                select(casework_parties).where(
                    casework_parties.c.matter_id == matter_id,
                    casework_parties.c.party_id == party_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return self._party_record(row)

    def require_party(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        party_id: UUID,
    ) -> PartyRecord:
        party = self.get_party(connection, matter_id=matter_id, party_id=party_id)
        if party is None:
            raise NotFoundError(f"party not found in matter: {party_id}")
        return party

    def insert_party_role(
        self,
        connection: Connection,
        *,
        role_id: UUID,
        matter_id: UUID,
        party_id: UUID,
        role: PartyRole,
    ) -> PartyRoleRecord:
        try:
            connection.execute(
                insert(casework_party_roles).values(
                    role_id=role_id,
                    matter_id=matter_id,
                    party_id=party_id,
                    role=role.value,
                )
            )
        except IntegrityError as exc:
            self._map_integrity_error(exc)
        row = (
            connection.execute(
                select(casework_party_roles).where(casework_party_roles.c.role_id == role_id)
            )
            .mappings()
            .one()
        )
        return self._party_role_record(row)

    def has_primary_subject(self, connection: Connection, matter_id: UUID) -> bool:
        row = connection.execute(
            select(casework_party_roles.c.role_id)
            .where(
                casework_party_roles.c.matter_id == matter_id,
                casework_party_roles.c.role == PartyRole.PRIMARY_SUBJECT.value,
            )
            .limit(1)
        ).first()
        return row is not None

    def insert_fact(
        self,
        connection: Connection,
        *,
        fact_id: UUID,
        matter_id: UUID,
        kind: FactKind,
        status: FactStatus,
        statement: str,
        source_ref: str | None,
        source_channel: str | None,
    ) -> FactItemRecord:
        try:
            connection.execute(
                insert(casework_fact_items).values(
                    fact_id=fact_id,
                    matter_id=matter_id,
                    kind=kind.value,
                    status=status.value,
                    statement=statement,
                    source_ref=source_ref,
                    source_channel=source_channel,
                    verified_by=None,
                    verified_at=None,
                    verification_method=None,
                    verification_source_ref=None,
                    verification_note=None,
                )
            )
        except IntegrityError as exc:
            self._map_integrity_error(exc)
        return self.require_fact(connection, matter_id=matter_id, fact_id=fact_id)

    def get_fact(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        fact_id: UUID,
    ) -> FactItemRecord | None:
        row = (
            connection.execute(
                select(casework_fact_items).where(
                    casework_fact_items.c.matter_id == matter_id,
                    casework_fact_items.c.fact_id == fact_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return self._fact_record(row)

    def require_fact(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        fact_id: UUID,
    ) -> FactItemRecord:
        fact = self.get_fact(connection, matter_id=matter_id, fact_id=fact_id)
        if fact is None:
            raise NotFoundError(f"fact not found in matter: {fact_id}")
        return fact

    def update_fact_status(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        fact_id: UUID,
        status: FactStatus,
        verified_by: str | None,
        verified_at: datetime | None,
        verification_method: VerificationMethod | None,
        verification_source_ref: str | None,
        verification_note: str | None,
    ) -> FactItemRecord:
        try:
            result = connection.execute(
                update(casework_fact_items)
                .where(
                    casework_fact_items.c.matter_id == matter_id,
                    casework_fact_items.c.fact_id == fact_id,
                )
                .values(
                    status=status.value,
                    verified_by=verified_by,
                    verified_at=verified_at,
                    verification_method=(
                        verification_method.value if verification_method is not None else None
                    ),
                    verification_source_ref=verification_source_ref,
                    verification_note=verification_note,
                )
            )
        except IntegrityError as exc:
            self._map_integrity_error(exc)
        if result.rowcount != 1:
            raise NotFoundError(f"fact not found in matter: {fact_id}")
        return self.require_fact(connection, matter_id=matter_id, fact_id=fact_id)

    def insert_issue(
        self,
        connection: Connection,
        *,
        issue_id: UUID,
        matter_id: UUID,
        issue_type: IssueType,
        status: IssueStatus,
        question_or_topic: str,
    ) -> IssueRecord:
        try:
            connection.execute(
                insert(casework_issues).values(
                    issue_id=issue_id,
                    matter_id=matter_id,
                    issue_type=issue_type.value,
                    status=status.value,
                    question_or_topic=question_or_topic,
                )
            )
        except IntegrityError as exc:
            self._map_integrity_error(exc)
        return self.require_issue(connection, matter_id=matter_id, issue_id=issue_id)

    def get_issue(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        issue_id: UUID,
    ) -> IssueRecord | None:
        row = (
            connection.execute(
                select(casework_issues).where(
                    casework_issues.c.matter_id == matter_id,
                    casework_issues.c.issue_id == issue_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return self._issue_record(row)

    def require_issue(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        issue_id: UUID,
    ) -> IssueRecord:
        issue = self.get_issue(connection, matter_id=matter_id, issue_id=issue_id)
        if issue is None:
            raise NotFoundError(f"issue not found in matter: {issue_id}")
        return issue

    def update_issue_status(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        issue_id: UUID,
        status: IssueStatus,
    ) -> IssueRecord:
        result = connection.execute(
            update(casework_issues)
            .where(
                casework_issues.c.matter_id == matter_id,
                casework_issues.c.issue_id == issue_id,
            )
            .values(status=status.value)
        )
        if result.rowcount != 1:
            raise NotFoundError(f"issue not found in matter: {issue_id}")
        return self.require_issue(connection, matter_id=matter_id, issue_id=issue_id)

    def insert_deadline(
        self,
        connection: Connection,
        *,
        deadline_id: UUID,
        matter_id: UUID,
        source_description: str,
        source_ref: str | None,
        jurisdiction: Jurisdiction,
        confidence: DeadlineConfidence,
        responsible_actor: str,
        timezone: str,
        precision: DeadlinePrecision,
        due_date: date | None,
        due_at: datetime | None,
        status: DeadlineStatus,
        human_confirmation_required: bool,
    ) -> DeadlineRecord:
        try:
            connection.execute(
                insert(casework_deadlines).values(
                    deadline_id=deadline_id,
                    matter_id=matter_id,
                    source_description=source_description,
                    source_ref=source_ref,
                    jurisdiction=jurisdiction.value,
                    confidence=confidence.value,
                    responsible_actor=responsible_actor,
                    timezone=timezone,
                    precision=precision.value,
                    due_date=due_date,
                    due_at=due_at,
                    status=status.value,
                    human_confirmation_required=human_confirmation_required,
                    confirmed_by=None,
                    confirmed_at=None,
                    confirmation_method=None,
                )
            )
        except IntegrityError as exc:
            self._map_integrity_error(exc)
        return self.require_deadline(connection, matter_id=matter_id, deadline_id=deadline_id)

    def get_deadline(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        deadline_id: UUID,
    ) -> DeadlineRecord | None:
        row = (
            connection.execute(
                select(casework_deadlines).where(
                    casework_deadlines.c.matter_id == matter_id,
                    casework_deadlines.c.deadline_id == deadline_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return self._deadline_record(row)

    def require_deadline(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        deadline_id: UUID,
    ) -> DeadlineRecord:
        deadline = self.get_deadline(connection, matter_id=matter_id, deadline_id=deadline_id)
        if deadline is None:
            raise NotFoundError(f"deadline not found in matter: {deadline_id}")
        return deadline

    def update_deadline(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        deadline_id: UUID,
        values: Mapping[str, Any],
    ) -> DeadlineRecord:
        try:
            result = connection.execute(
                update(casework_deadlines)
                .where(
                    casework_deadlines.c.matter_id == matter_id,
                    casework_deadlines.c.deadline_id == deadline_id,
                )
                .values(**values)
            )
        except IntegrityError as exc:
            self._map_integrity_error(exc)
        if result.rowcount != 1:
            raise NotFoundError(f"deadline not found in matter: {deadline_id}")
        return self.require_deadline(connection, matter_id=matter_id, deadline_id=deadline_id)

    def insert_task(
        self,
        connection: Connection,
        *,
        task_id: UUID,
        matter_id: UUID,
        title: str,
        status: TaskStatus,
        deadline_id: UUID | None,
    ) -> TaskRecord:
        try:
            connection.execute(
                insert(casework_tasks).values(
                    task_id=task_id,
                    matter_id=matter_id,
                    title=title,
                    status=status.value,
                    deadline_id=deadline_id,
                )
            )
        except IntegrityError as exc:
            self._map_integrity_error(exc)
        return self.require_task(connection, matter_id=matter_id, task_id=task_id)

    def get_task(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        task_id: UUID,
    ) -> TaskRecord | None:
        row = (
            connection.execute(
                select(casework_tasks).where(
                    casework_tasks.c.matter_id == matter_id,
                    casework_tasks.c.task_id == task_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return self._task_record(row)

    def require_task(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        task_id: UUID,
    ) -> TaskRecord:
        task = self.get_task(connection, matter_id=matter_id, task_id=task_id)
        if task is None:
            raise NotFoundError(f"task not found in matter: {task_id}")
        return task

    def update_task_status(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        task_id: UUID,
        status: TaskStatus,
    ) -> TaskRecord:
        result = connection.execute(
            update(casework_tasks)
            .where(
                casework_tasks.c.matter_id == matter_id,
                casework_tasks.c.task_id == task_id,
            )
            .values(status=status.value)
        )
        if result.rowcount != 1:
            raise NotFoundError(f"task not found in matter: {task_id}")
        return self.require_task(connection, matter_id=matter_id, task_id=task_id)

    def append_audit_event(
        self,
        connection: Connection,
        *,
        event_id: UUID,
        matter_id: UUID,
        actor: str,
        event_type: AuditEventType,
        entity_type: str,
        entity_id: UUID | None,
        correlation_id: UUID | None,
        reason: str | None,
        source_channel: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> AuditEventRecord:
        payload = validate_audit_metadata(dict(metadata or {}))
        try:
            connection.execute(
                insert(casework_audit_events).values(
                    event_id=event_id,
                    matter_id=matter_id,
                    actor=actor,
                    event_type=event_type.value,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    correlation_id=correlation_id,
                    reason=reason,
                    source_channel=source_channel,
                    metadata=payload,
                )
            )
        except IntegrityError as exc:
            self._map_integrity_error(exc)
        row = (
            connection.execute(
                select(casework_audit_events).where(casework_audit_events.c.event_id == event_id)
            )
            .mappings()
            .one()
        )
        return self._audit_record(row)

    def list_audit_events(
        self,
        connection: Connection,
        matter_id: UUID,
    ) -> list[AuditEventRecord]:
        rows = (
            connection.execute(
                select(casework_audit_events)
                .where(casework_audit_events.c.matter_id == matter_id)
                .order_by(casework_audit_events.c.occurred_at)
            )
            .mappings()
            .all()
        )
        return [self._audit_record(row) for row in rows]

    @staticmethod
    def _map_integrity_error(
        exc: IntegrityError,
        *,
        reference_conflict: bool = False,
    ) -> None:
        message = str(exc.orig) if exc.orig is not None else str(exc)
        lowered = message.lower()
        if reference_conflict and "uq_casework_matters_reference" in lowered:
            raise ReferenceAllocationError("matter reference unique constraint violated") from exc
        if "uq_casework_matters_reference" in lowered:
            raise ReferenceAllocationError("matter reference unique constraint violated") from exc
        if "foreign key" in lowered or "fk_casework" in lowered:
            raise CrossMatterViolationError(
                "cross-matter or missing parent relationship rejected"
            ) from exc
        raise CaseworkValidationError(f"database constraint rejected write: {message}") from exc

    @staticmethod
    def _matter_record(row: RowMapping) -> MatterRecord:
        return MatterRecord(
            matter_id=cast(UUID, row["matter_id"]),
            reference=cast(str, row["reference"]),
            title=cast(str, row["title"]),
            summary=cast(str | None, row["summary"]),
            status=MatterStatus(cast(str, row["status"])),
            jurisdiction=Jurisdiction(cast(str, row["jurisdiction"])),
            case_type=CaseType(cast(str, row["case_type"])),
            risk_level=RiskLevel(cast(str, row["risk_level"])),
            action_authority_ceiling=ActionAuthorityLevel(
                cast(str, row["action_authority_ceiling"])
            ),
            row_version=cast(int, row["row_version"]),
            created_by=cast(str, row["created_by"]),
            updated_by=cast(str, row["updated_by"]),
            created_at=cast(datetime, row["created_at"]),
            updated_at=cast(datetime, row["updated_at"]),
            closed_at=cast(datetime | None, row["closed_at"]),
            assigned_playbook_version_id=cast(UUID | None, row["assigned_playbook_version_id"]),
            playbook_assigned_at=cast(datetime | None, row["playbook_assigned_at"]),
            playbook_assigned_by=cast(str | None, row["playbook_assigned_by"]),
        )

    @staticmethod
    def _party_record(row: RowMapping) -> PartyRecord:
        return PartyRecord(
            party_id=cast(UUID, row["party_id"]),
            matter_id=cast(UUID, row["matter_id"]),
            entity_type=PartyEntityType(cast(str, row["entity_type"])),
            display_name=cast(str, row["display_name"]),
            created_at=cast(datetime, row["created_at"]),
        )

    @staticmethod
    def _party_role_record(row: RowMapping) -> PartyRoleRecord:
        return PartyRoleRecord(
            role_id=cast(UUID, row["role_id"]),
            matter_id=cast(UUID, row["matter_id"]),
            party_id=cast(UUID, row["party_id"]),
            role=PartyRole(cast(str, row["role"])),
            created_at=cast(datetime, row["created_at"]),
        )

    @staticmethod
    def _fact_record(row: RowMapping) -> FactItemRecord:
        method_raw = cast(str | None, row["verification_method"])
        return FactItemRecord(
            fact_id=cast(UUID, row["fact_id"]),
            matter_id=cast(UUID, row["matter_id"]),
            kind=FactKind(cast(str, row["kind"])),
            status=FactStatus(cast(str, row["status"])),
            statement=cast(str, row["statement"]),
            source_ref=cast(str | None, row["source_ref"]),
            source_channel=cast(str | None, row["source_channel"]),
            verified_by=cast(str | None, row["verified_by"]),
            verified_at=cast(datetime | None, row["verified_at"]),
            verification_method=(
                VerificationMethod(method_raw) if method_raw is not None else None
            ),
            verification_source_ref=cast(str | None, row["verification_source_ref"]),
            verification_note=cast(str | None, row["verification_note"]),
            created_at=cast(datetime, row["created_at"]),
        )

    @staticmethod
    def _issue_record(row: RowMapping) -> IssueRecord:
        return IssueRecord(
            issue_id=cast(UUID, row["issue_id"]),
            matter_id=cast(UUID, row["matter_id"]),
            issue_type=IssueType(cast(str, row["issue_type"])),
            status=IssueStatus(cast(str, row["status"])),
            question_or_topic=cast(str, row["question_or_topic"]),
            created_at=cast(datetime, row["created_at"]),
        )

    @staticmethod
    def _deadline_record(row: RowMapping) -> DeadlineRecord:
        method_raw = cast(str | None, row["confirmation_method"])
        return DeadlineRecord(
            deadline_id=cast(UUID, row["deadline_id"]),
            matter_id=cast(UUID, row["matter_id"]),
            source_description=cast(str, row["source_description"]),
            source_ref=cast(str | None, row["source_ref"]),
            jurisdiction=Jurisdiction(cast(str, row["jurisdiction"])),
            confidence=DeadlineConfidence(cast(str, row["confidence"])),
            responsible_actor=cast(str, row["responsible_actor"]),
            timezone=cast(str, row["timezone"]),
            precision=DeadlinePrecision(cast(str, row["precision"])),
            due_date=cast(date | None, row["due_date"]),
            due_at=cast(datetime | None, row["due_at"]),
            status=DeadlineStatus(cast(str, row["status"])),
            human_confirmation_required=cast(bool, row["human_confirmation_required"]),
            confirmed_by=cast(str | None, row["confirmed_by"]),
            confirmed_at=cast(datetime | None, row["confirmed_at"]),
            confirmation_method=(
                ConfirmationMethod(method_raw) if method_raw is not None else None
            ),
            created_at=cast(datetime, row["created_at"]),
        )

    @staticmethod
    def _task_record(row: RowMapping) -> TaskRecord:
        return TaskRecord(
            task_id=cast(UUID, row["task_id"]),
            matter_id=cast(UUID, row["matter_id"]),
            title=cast(str, row["title"]),
            status=TaskStatus(cast(str, row["status"])),
            deadline_id=cast(UUID | None, row["deadline_id"]),
            created_at=cast(datetime, row["created_at"]),
        )

    @staticmethod
    def _audit_record(row: RowMapping) -> AuditEventRecord:
        metadata = cast(dict[str, Any], row["metadata"])
        return AuditEventRecord(
            event_id=cast(UUID, row["event_id"]),
            matter_id=cast(UUID, row["matter_id"]),
            actor=cast(str, row["actor"]),
            event_type=AuditEventType(cast(str, row["event_type"])),
            entity_type=cast(str, row["entity_type"]),
            entity_id=cast(UUID | None, row["entity_id"]),
            occurred_at=cast(datetime, row["occurred_at"]),
            correlation_id=cast(UUID | None, row["correlation_id"]),
            reason=cast(str | None, row["reason"]),
            source_channel=cast(str, row["source_channel"]),
            metadata=dict(metadata),
        )

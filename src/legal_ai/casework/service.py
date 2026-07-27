"""Application service for Phase 1 Generic Casework Core."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID, uuid4

from sqlalchemy import Connection

from legal_ai.casework.authority import assert_action_allowed
from legal_ai.casework.errors import (
    ActionAuthorityDenied,
    AuditWriteFailed,
    CaseworkValidationError,
    ClosedMatterMutationError,
    NotFoundError,
)
from legal_ai.casework.models import (
    AddDeadlineCommand,
    AddFactCommand,
    AddIssueCommand,
    AddPartyCommand,
    AddTaskCommand,
    AssignRoleCommand,
    AuditEventRecord,
    ConfirmDeadlineCommand,
    CreateMatterCommand,
    DeadlineRecord,
    FactItemRecord,
    IssueRecord,
    MatterRecord,
    PartyRecord,
    PartyRoleRecord,
    ReopenMatterCommand,
    TaskRecord,
    TransitionMatterCommand,
    UpdateDeadlineDueCommand,
    UpdateFactStatusCommand,
    UpdateIssueStatusCommand,
    UpdateMatterCommand,
    UpdateTaskStatusCommand,
)
from legal_ai.casework.repository import CaseworkRepository
from legal_ai.casework.state_machine import assert_transition_allowed
from legal_ai.casework.types import (
    ActionAuthorityLevel,
    AuditEventType,
    FactKind,
    FactStatus,
    MatterStatus,
)

T = TypeVar("T")


class CaseworkService:
    """Command handlers enforcing authority, lifecycle, and audit atomicity."""

    def __init__(self, repository: CaseworkRepository) -> None:
        self._repository = repository

    def create_matter(self, command: CreateMatterCommand) -> MatterRecord:
        matter_id = uuid4()
        with self._repository.transaction() as connection:
            reference = self._repository.allocate_reference(connection)
            matter = self._repository.insert_matter(
                connection,
                matter_id=matter_id,
                reference=reference,
                title=command.title,
                summary=command.summary,
                jurisdiction=command.jurisdiction,
                case_type=command.case_type,
                risk_level=command.risk_level,
                action_authority_ceiling=command.action_authority_ceiling,
                actor=command.actor,
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=matter_id,
                actor=command.actor,
                event_type=AuditEventType.MATTER_CREATED,
                entity_type="matter",
                entity_id=matter_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={"command_type": "CreateMatter"},
            )
            return matter

    def get_matter(self, matter_id: UUID, *, actor: str, source_channel: str) -> MatterRecord:
        with self._repository.transaction() as connection:
            matter = self._repository.require_matter(connection, matter_id)
            self._assert_allowed(
                required=ActionAuthorityLevel.L0,
                ceiling=matter.action_authority_ceiling,
                command_type="GetMatter",
                matter_id=matter_id,
                actor=actor,
                source_channel=source_channel,
            )
            return matter

    def update_matter(self, command: UpdateMatterCommand) -> MatterRecord:
        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="UpdateMatter",
            correlation_id=command.correlation_id,
            execute=lambda connection, matter: self._do_update_matter(connection, matter, command),
        )

    def transition_matter(self, command: TransitionMatterCommand) -> MatterRecord:
        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="TransitionMatter",
            correlation_id=command.correlation_id,
            execute=lambda connection, matter: self._do_transition(connection, matter, command),
        )

    def reopen_matter(self, command: ReopenMatterCommand) -> MatterRecord:
        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="ReopenMatter",
            correlation_id=command.correlation_id,
            allow_closed=True,
            execute=lambda connection, matter: self._do_reopen(connection, matter, command),
        )

    def add_party(self, command: AddPartyCommand) -> PartyRecord:
        party_id = uuid4()

        def _execute(connection: Connection, _matter: MatterRecord) -> PartyRecord:
            party = self._repository.insert_party(
                connection,
                party_id=party_id,
                matter_id=command.matter_id,
                entity_type=command.entity_type,
                display_name=command.display_name,
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.PARTY_ADDED,
                entity_type="party",
                entity_id=party_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "AddParty",
                    "party_id": str(party_id),
                },
            )
            return party

        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="AddParty",
            correlation_id=command.correlation_id,
            execute=_execute,
        )

    def assign_role(self, command: AssignRoleCommand) -> PartyRoleRecord:
        role_id = uuid4()

        def _execute(connection: Connection, _matter: MatterRecord) -> PartyRoleRecord:
            self._repository.require_party(
                connection, matter_id=command.matter_id, party_id=command.party_id
            )
            role = self._repository.insert_party_role(
                connection,
                role_id=role_id,
                matter_id=command.matter_id,
                party_id=command.party_id,
                role=command.role,
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.PARTY_ROLE_ASSIGNED,
                entity_type="party_role",
                entity_id=role_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "AssignRole",
                    "party_id": str(command.party_id),
                    "role": command.role.value,
                },
            )
            return role

        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="AssignRole",
            correlation_id=command.correlation_id,
            execute=_execute,
        )

    def add_fact(self, command: AddFactCommand) -> FactItemRecord:
        fact_id = uuid4()

        def _execute(connection: Connection, _matter: MatterRecord) -> FactItemRecord:
            fact = self._repository.insert_fact(
                connection,
                fact_id=fact_id,
                matter_id=command.matter_id,
                kind=command.kind,
                status=command.status,
                statement=command.statement,
                source_ref=command.source_ref,
                source_channel=command.source_channel,
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.FACT_ADDED,
                entity_type="fact",
                entity_id=fact_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "AddFact",
                    "fact_id": str(fact_id),
                },
            )
            return fact

        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="AddFact",
            correlation_id=command.correlation_id,
            execute=_execute,
        )

    def update_fact_status(self, command: UpdateFactStatusCommand) -> FactItemRecord:
        def _execute(connection: Connection, _matter: MatterRecord) -> FactItemRecord:
            existing = self._repository.require_fact(
                connection, matter_id=command.matter_id, fact_id=command.fact_id
            )
            if command.status is FactStatus.VERIFIED and existing.kind is FactKind.ASSUMPTION:
                raise CaseworkValidationError("ASSUMPTION facts cannot become VERIFIED")
            updated = self._repository.update_fact_status(
                connection,
                matter_id=command.matter_id,
                fact_id=command.fact_id,
                status=command.status,
                verified_by=command.verified_by,
                verified_at=command.verified_at,
                verification_method=command.verification_method,
                verification_source_ref=command.verification_source_ref,
                verification_note=command.verification_note,
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.FACT_STATUS_CHANGED,
                entity_type="fact",
                entity_id=command.fact_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "UpdateFactStatus",
                    "fact_id": str(command.fact_id),
                    "from_fact_status": existing.status.value,
                    "to_fact_status": command.status.value,
                },
            )
            return updated

        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="UpdateFactStatus",
            correlation_id=command.correlation_id,
            execute=_execute,
        )

    def add_issue(self, command: AddIssueCommand) -> IssueRecord:
        issue_id = uuid4()

        def _execute(connection: Connection, _matter: MatterRecord) -> IssueRecord:
            issue = self._repository.insert_issue(
                connection,
                issue_id=issue_id,
                matter_id=command.matter_id,
                issue_type=command.issue_type,
                status=command.status,
                question_or_topic=command.question_or_topic,
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.ISSUE_ADDED,
                entity_type="issue",
                entity_id=issue_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "AddIssue",
                    "issue_id": str(issue_id),
                },
            )
            return issue

        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="AddIssue",
            correlation_id=command.correlation_id,
            execute=_execute,
        )

    def update_issue_status(self, command: UpdateIssueStatusCommand) -> IssueRecord:
        def _execute(connection: Connection, _matter: MatterRecord) -> IssueRecord:
            existing = self._repository.require_issue(
                connection, matter_id=command.matter_id, issue_id=command.issue_id
            )
            updated = self._repository.update_issue_status(
                connection,
                matter_id=command.matter_id,
                issue_id=command.issue_id,
                status=command.status,
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.ISSUE_STATUS_CHANGED,
                entity_type="issue",
                entity_id=command.issue_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "UpdateIssueStatus",
                    "issue_id": str(command.issue_id),
                    "from_issue_status": existing.status.value,
                    "to_issue_status": command.status.value,
                },
            )
            return updated

        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="UpdateIssueStatus",
            correlation_id=command.correlation_id,
            execute=_execute,
        )

    def add_deadline(self, command: AddDeadlineCommand) -> DeadlineRecord:
        deadline_id = uuid4()

        def _execute(connection: Connection, _matter: MatterRecord) -> DeadlineRecord:
            deadline = self._repository.insert_deadline(
                connection,
                deadline_id=deadline_id,
                matter_id=command.matter_id,
                source_description=command.source_description,
                source_ref=command.source_ref,
                jurisdiction=command.jurisdiction,
                confidence=command.confidence,
                responsible_actor=command.responsible_actor,
                timezone=command.timezone,
                precision=command.precision,
                due_date=command.due_date,
                due_at=command.due_at,
                status=command.status,
                human_confirmation_required=command.human_confirmation_required,
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.DEADLINE_ADDED,
                entity_type="deadline",
                entity_id=deadline_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "AddDeadline",
                    "deadline_id": str(deadline_id),
                    "precision": command.precision.value,
                    "timezone": command.timezone,
                },
            )
            return deadline

        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="AddDeadline",
            correlation_id=command.correlation_id,
            execute=_execute,
        )

    def confirm_deadline(self, command: ConfirmDeadlineCommand) -> DeadlineRecord:
        def _execute(connection: Connection, _matter: MatterRecord) -> DeadlineRecord:
            self._repository.require_deadline(
                connection, matter_id=command.matter_id, deadline_id=command.deadline_id
            )
            confirmed_at = command.confirmed_at or datetime.now(UTC)
            updated = self._repository.update_deadline(
                connection,
                matter_id=command.matter_id,
                deadline_id=command.deadline_id,
                values={
                    "confirmed_by": command.confirmed_by,
                    "confirmed_at": confirmed_at,
                    "confirmation_method": command.confirmation_method.value,
                },
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.DEADLINE_CONFIRMED,
                entity_type="deadline",
                entity_id=command.deadline_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "ConfirmDeadline",
                    "deadline_id": str(command.deadline_id),
                },
            )
            return updated

        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="ConfirmDeadline",
            correlation_id=command.correlation_id,
            execute=_execute,
        )

    def update_deadline_due(self, command: UpdateDeadlineDueCommand) -> DeadlineRecord:
        def _execute(connection: Connection, _matter: MatterRecord) -> DeadlineRecord:
            existing = self._repository.require_deadline(
                connection, matter_id=command.matter_id, deadline_id=command.deadline_id
            )
            updated = self._repository.update_deadline(
                connection,
                matter_id=command.matter_id,
                deadline_id=command.deadline_id,
                values={
                    "timezone": command.timezone,
                    "precision": command.precision.value,
                    "due_date": command.due_date,
                    "due_at": command.due_at,
                    "confirmed_by": None,
                    "confirmed_at": None,
                    "confirmation_method": None,
                },
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.DEADLINE_DUE_VALUE_CHANGED,
                entity_type="deadline",
                entity_id=command.deadline_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "UpdateDeadlineDue",
                    "deadline_id": str(command.deadline_id),
                    "precision": command.precision.value,
                    "timezone": command.timezone,
                },
            )
            if (
                existing.confirmed_by is not None
                or existing.confirmed_at is not None
                or existing.confirmation_method is not None
            ):
                self._append_audit(
                    connection,
                    event_id=uuid4(),
                    matter_id=command.matter_id,
                    actor=command.actor,
                    event_type=AuditEventType.DEADLINE_CONFIRMATION_CLEARED,
                    entity_type="deadline",
                    entity_id=command.deadline_id,
                    correlation_id=command.correlation_id,
                    reason=None,
                    source_channel=command.source_channel,
                    metadata={
                        "command_type": "UpdateDeadlineDue",
                        "deadline_id": str(command.deadline_id),
                    },
                )
            return updated

        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="UpdateDeadlineDue",
            correlation_id=command.correlation_id,
            execute=_execute,
        )

    def add_task(self, command: AddTaskCommand) -> TaskRecord:
        task_id = uuid4()

        def _execute(connection: Connection, _matter: MatterRecord) -> TaskRecord:
            if command.deadline_id is not None:
                self._repository.require_deadline(
                    connection,
                    matter_id=command.matter_id,
                    deadline_id=command.deadline_id,
                )
            task = self._repository.insert_task(
                connection,
                task_id=task_id,
                matter_id=command.matter_id,
                title=command.title,
                status=command.status,
                deadline_id=command.deadline_id,
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.TASK_ADDED,
                entity_type="task",
                entity_id=task_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "AddTask",
                    "task_id": str(task_id),
                },
            )
            return task

        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="AddTask",
            correlation_id=command.correlation_id,
            execute=_execute,
        )

    def update_task_status(self, command: UpdateTaskStatusCommand) -> TaskRecord:
        def _execute(connection: Connection, _matter: MatterRecord) -> TaskRecord:
            existing = self._repository.require_task(
                connection, matter_id=command.matter_id, task_id=command.task_id
            )
            updated = self._repository.update_task_status(
                connection,
                matter_id=command.matter_id,
                task_id=command.task_id,
                status=command.status,
            )
            self._append_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.TASK_STATUS_CHANGED,
                entity_type="task",
                entity_id=command.task_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "UpdateTaskStatus",
                    "task_id": str(command.task_id),
                    "from_task_status": existing.status.value,
                    "to_task_status": command.status.value,
                },
            )
            return updated

        return self._mutate(
            matter_id=command.matter_id,
            actor=command.actor,
            source_channel=command.source_channel,
            command_type="UpdateTaskStatus",
            correlation_id=command.correlation_id,
            execute=_execute,
        )

    def list_audit_events(self, matter_id: UUID) -> list[AuditEventRecord]:
        with self._repository.transaction() as connection:
            self._repository.require_matter(connection, matter_id)
            return self._repository.list_audit_events(connection, matter_id)

    def _do_update_matter(
        self,
        connection: Connection,
        matter: MatterRecord,
        command: UpdateMatterCommand,
    ) -> MatterRecord:
        del matter  # loaded for authority/closed checks in _mutate
        values: dict[str, object] = {"updated_by": command.actor}
        if command.title is not None:
            values["title"] = command.title
        if command.summary is not None:
            values["summary"] = command.summary
        if command.jurisdiction is not None:
            values["jurisdiction"] = command.jurisdiction.value
        if command.case_type is not None:
            values["case_type"] = command.case_type.value
        if command.risk_level is not None:
            values["risk_level"] = command.risk_level.value
        updated = self._repository.update_matter_optimistic(
            connection,
            matter_id=command.matter_id,
            expected_row_version=command.row_version,
            values=values,
        )
        self._append_audit(
            connection,
            event_id=uuid4(),
            matter_id=command.matter_id,
            actor=command.actor,
            event_type=AuditEventType.MATTER_UPDATED,
            entity_type="matter",
            entity_id=command.matter_id,
            correlation_id=command.correlation_id,
            reason=None,
            source_channel=command.source_channel,
            metadata={
                "command_type": "UpdateMatter",
                "row_version": updated.row_version,
            },
        )
        return updated

    def _do_transition(
        self,
        connection: Connection,
        matter: MatterRecord,
        command: TransitionMatterCommand,
    ) -> MatterRecord:
        assert_transition_allowed(
            current=matter.status,
            target=command.target_status,
            case_type=matter.case_type,
            reopen=False,
        )
        if (
            matter.status is MatterStatus.INTAKE_INCOMPLETE
            and command.target_status is MatterStatus.INTAKE_COMPLETE
            and not self._repository.has_primary_subject(connection, command.matter_id)
        ):
            raise CaseworkValidationError(
                "INTAKE_COMPLETE requires at least one PRIMARY_SUBJECT role"
            )
        values: dict[str, object] = {
            "status": command.target_status.value,
            "updated_by": command.actor,
        }
        if command.target_status is MatterStatus.CLOSED:
            values["closed_at"] = datetime.now(UTC)
        updated = self._repository.update_matter_optimistic(
            connection,
            matter_id=command.matter_id,
            expected_row_version=command.row_version,
            values=values,
        )
        self._append_audit(
            connection,
            event_id=uuid4(),
            matter_id=command.matter_id,
            actor=command.actor,
            event_type=AuditEventType.MATTER_STATUS_CHANGED,
            entity_type="matter",
            entity_id=command.matter_id,
            correlation_id=command.correlation_id,
            reason=command.reason,
            source_channel=command.source_channel,
            metadata={
                "command_type": "TransitionMatter",
                "from_status": matter.status.value,
                "to_status": command.target_status.value,
            },
        )
        return updated

    def _do_reopen(
        self,
        connection: Connection,
        matter: MatterRecord,
        command: ReopenMatterCommand,
    ) -> MatterRecord:
        if matter.status is not MatterStatus.CLOSED:
            raise CaseworkValidationError("ReopenMatter requires a CLOSED matter")
        assert_transition_allowed(
            current=matter.status,
            target=command.target_status,
            case_type=matter.case_type,
            reopen=True,
        )
        updated = self._repository.update_matter_optimistic(
            connection,
            matter_id=command.matter_id,
            expected_row_version=command.row_version,
            values={
                "status": command.target_status.value,
                "closed_at": None,
                "updated_by": command.actor,
            },
        )
        self._append_audit(
            connection,
            event_id=uuid4(),
            matter_id=command.matter_id,
            actor=command.actor,
            event_type=AuditEventType.MATTER_REOPENED,
            entity_type="matter",
            entity_id=command.matter_id,
            correlation_id=command.correlation_id,
            reason=command.reason,
            source_channel=command.source_channel,
            metadata={
                "command_type": "ReopenMatter",
                "from_status": MatterStatus.CLOSED.value,
                "to_status": command.target_status.value,
            },
        )
        return updated

    def _mutate(
        self,
        *,
        matter_id: UUID,
        actor: str,
        source_channel: str,
        command_type: str,
        correlation_id: UUID | None,
        execute: Callable[[Connection, MatterRecord], T],
        allow_closed: bool = False,
    ) -> T:
        with self._repository.transaction() as connection:
            matter = self._repository.require_matter(connection, matter_id)
            self._assert_allowed(
                required=ActionAuthorityLevel.L1,
                ceiling=matter.action_authority_ceiling,
                command_type=command_type,
                matter_id=matter_id,
                actor=actor,
                source_channel=source_channel,
                correlation_id=correlation_id,
            )
            if matter.status is MatterStatus.CLOSED and not allow_closed:
                raise ClosedMatterMutationError(f"{command_type} is not allowed on CLOSED matters")
            return execute(connection, matter)

    def _assert_allowed(
        self,
        *,
        required: ActionAuthorityLevel,
        ceiling: ActionAuthorityLevel,
        command_type: str,
        matter_id: UUID | None,
        actor: str,
        source_channel: str,
        correlation_id: UUID | None = None,
    ) -> None:
        try:
            assert_action_allowed(
                required=required,
                ceiling=ceiling,
                command_type=command_type,
            )
        except ActionAuthorityDenied as denied:
            self._record_denial(
                denied=denied,
                matter_id=matter_id,
                actor=actor,
                source_channel=source_channel,
                correlation_id=correlation_id,
            )
            raise

    def _record_denial(
        self,
        *,
        denied: ActionAuthorityDenied,
        matter_id: UUID | None,
        actor: str,
        source_channel: str,
        correlation_id: UUID | None,
    ) -> None:
        if matter_id is None:
            return
        try:
            with self._repository.transaction() as connection:
                self._repository.require_matter(connection, matter_id)
                self._repository.append_audit_event(
                    connection,
                    event_id=uuid4(),
                    matter_id=matter_id,
                    actor=actor,
                    event_type=AuditEventType.ACTION_DENIED,
                    entity_type="matter",
                    entity_id=matter_id,
                    correlation_id=correlation_id,
                    reason=None,
                    source_channel=source_channel,
                    metadata={
                        "command_type": denied.command_type,
                        "required_level": denied.required.value,
                        "ceiling": (denied.ceiling.value if denied.ceiling is not None else "none"),
                    },
                )
        except NotFoundError:
            return
        except Exception:
            raise AuditWriteFailed("denial audit insert failed") from denied

    def _append_audit(
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
        metadata: dict[str, object],
    ) -> AuditEventRecord:
        try:
            return self._repository.append_audit_event(
                connection,
                event_id=event_id,
                matter_id=matter_id,
                actor=actor,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=correlation_id,
                reason=reason,
                source_channel=source_channel,
                metadata=metadata,
            )
        except Exception as exc:
            raise AuditWriteFailed(f"audit insert failed for {event_type.value}") from exc

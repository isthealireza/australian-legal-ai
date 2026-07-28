"""SQLAlchemy Core repository for Phase 2 Versioned Playbook Framework."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, RowMapping, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from legal_ai.casework.errors import ConcurrencyConflictError, NotFoundError
from legal_ai.db import (
    casework_checklist_states,
    casework_checklist_states_history,
    casework_intake_answers,
    casework_intake_answers_history,
    casework_playbook_evaluation_candidates,
    casework_playbook_evaluations,
    playbook_audit_events,
    playbook_versions,
    playbooks,
)
from legal_ai.db.transactions import independent_transaction
from legal_ai.playbooks.errors import PlaybookNotFoundError, PlaybookValidationError
from legal_ai.playbooks.models import (
    ChecklistStateRecord,
    EvaluationRecord,
    IntakeAnswerRecord,
    PlaybookAuditEventRecord,
    PlaybookVersionRecord,
    validate_playbook_audit_metadata,
)
from legal_ai.playbooks.types import (
    ChecklistItemStatus,
    EvaluationOutcome,
    EvaluationReason,
    IntakeValueType,
    PlaybookAuditEventType,
    PlaybookStatus,
    RuleResult,
)


class PlaybookRepository:
    """Playbook registry and matter-playbook persistence (SQLAlchemy Core)."""

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

    @contextmanager
    def independent_transaction(self) -> Iterator[Connection]:
        """Commit independently of any transaction owned by the caller."""

        with independent_transaction(self._bind) as connection:
            yield connection

    def ensure_playbook_family(
        self,
        connection: Connection,
        *,
        playbook_key: str,
        display_name: str,
        created_by: str,
    ) -> None:
        connection.execute(
            insert(playbooks)
            .values(
                playbook_key=playbook_key,
                display_name=display_name,
                created_by=created_by,
            )
            .on_conflict_do_nothing(index_elements=["playbook_key"])
        )

    def insert_draft_version(
        self,
        connection: Connection,
        *,
        playbook_version_id: UUID,
        playbook_key: str,
        version: int,
        schema_version: int,
        definition_json: Mapping[str, Any],
        content_sha256: str,
        actor: str,
    ) -> PlaybookVersionRecord:
        try:
            connection.execute(
                insert(playbook_versions).values(
                    playbook_version_id=playbook_version_id,
                    playbook_key=playbook_key,
                    version=version,
                    status=PlaybookStatus.DRAFT.value,
                    schema_version=schema_version,
                    definition_json=dict(definition_json),
                    content_sha256=content_sha256,
                    created_by=actor,
                    updated_by=actor,
                )
            )
        except IntegrityError as exc:
            raise PlaybookValidationError(
                f"draft insert rejected: {exc.orig if exc.orig is not None else exc}"
            ) from exc
        return self.require_version(connection, playbook_version_id)

    def update_draft(
        self,
        connection: Connection,
        *,
        playbook_version_id: UUID,
        expected_row_version: int,
        definition_json: Mapping[str, Any],
        content_sha256: str,
        actor: str,
    ) -> PlaybookVersionRecord:
        result = connection.execute(
            update(playbook_versions)
            .where(
                playbook_versions.c.playbook_version_id == playbook_version_id,
                playbook_versions.c.row_version == expected_row_version,
                playbook_versions.c.status == PlaybookStatus.DRAFT.value,
            )
            .values(
                definition_json=dict(definition_json),
                content_sha256=content_sha256,
                updated_by=actor,
                updated_at=func.now(),
                row_version=expected_row_version + 1,
            )
        )
        if result.rowcount != 1:
            raise ConcurrencyConflictError(
                f"playbook draft {playbook_version_id} row_version conflict "
                f"at {expected_row_version}"
            )
        return self.require_version(connection, playbook_version_id)

    def get_version(
        self,
        connection: Connection,
        playbook_version_id: UUID,
    ) -> PlaybookVersionRecord | None:
        row = (
            connection.execute(
                select(playbook_versions).where(
                    playbook_versions.c.playbook_version_id == playbook_version_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return self._version_record(row)

    def require_version(
        self,
        connection: Connection,
        playbook_version_id: UUID,
    ) -> PlaybookVersionRecord:
        version = self.get_version(connection, playbook_version_id)
        if version is None:
            raise PlaybookNotFoundError(f"playbook version not found: {playbook_version_id}")
        return version

    def get_version_by_key_version(
        self,
        connection: Connection,
        *,
        playbook_key: str,
        version: int,
    ) -> PlaybookVersionRecord | None:
        row = (
            connection.execute(
                select(playbook_versions).where(
                    playbook_versions.c.playbook_key == playbook_key,
                    playbook_versions.c.version == version,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return self._version_record(row)

    def list_active_versions(self, connection: Connection) -> list[PlaybookVersionRecord]:
        rows = (
            connection.execute(
                select(playbook_versions)
                .where(playbook_versions.c.status == PlaybookStatus.ACTIVE.value)
                .order_by(
                    playbook_versions.c.playbook_key.asc(),
                    playbook_versions.c.version.desc(),
                )
            )
            .mappings()
            .all()
        )
        return [self._version_record(row) for row in rows]

    def activate_version(
        self,
        connection: Connection,
        *,
        playbook_version_id: UUID,
        expected_row_version: int,
        activated_by: str,
        activated_at: datetime,
        effective_from: datetime | None,
    ) -> PlaybookVersionRecord:
        """UPDATE activation columns only. Caller must have passed grounding gate."""

        result = connection.execute(
            update(playbook_versions)
            .where(
                playbook_versions.c.playbook_version_id == playbook_version_id,
                playbook_versions.c.row_version == expected_row_version,
                playbook_versions.c.status == PlaybookStatus.DRAFT.value,
            )
            .values(
                status=PlaybookStatus.ACTIVE.value,
                activated_by=activated_by,
                activated_at=activated_at,
                effective_from=effective_from if effective_from is not None else activated_at,
                row_version=expected_row_version + 1,
            )
        )
        if result.rowcount != 1:
            raise ConcurrencyConflictError(
                f"playbook activate {playbook_version_id} conflict at {expected_row_version}"
            )
        return self.require_version(connection, playbook_version_id)

    def retire_version(
        self,
        connection: Connection,
        *,
        playbook_version_id: UUID,
        expected_row_version: int,
        retired_by: str,
        retired_at: datetime,
        retirement_reason_code: str,
    ) -> PlaybookVersionRecord:
        result = connection.execute(
            update(playbook_versions)
            .where(
                playbook_versions.c.playbook_version_id == playbook_version_id,
                playbook_versions.c.row_version == expected_row_version,
                playbook_versions.c.status == PlaybookStatus.ACTIVE.value,
            )
            .values(
                status=PlaybookStatus.RETIRED.value,
                retired_by=retired_by,
                retired_at=retired_at,
                retirement_reason_code=retirement_reason_code,
                row_version=expected_row_version + 1,
            )
        )
        if result.rowcount != 1:
            raise ConcurrencyConflictError(
                f"playbook retire {playbook_version_id} conflict at {expected_row_version}"
            )
        return self.require_version(connection, playbook_version_id)

    def append_playbook_audit(
        self,
        connection: Connection,
        *,
        event_id: UUID,
        playbook_key: str,
        version: int,
        playbook_version_id: UUID,
        actor: str,
        event_type: PlaybookAuditEventType,
        correlation_id: UUID | None,
        row_version_after: int | None,
        metadata: Mapping[str, Any] | None = None,
    ) -> PlaybookAuditEventRecord:
        payload = validate_playbook_audit_metadata(dict(metadata or {}))
        try:
            connection.execute(
                insert(playbook_audit_events).values(
                    event_id=event_id,
                    playbook_key=playbook_key,
                    version=version,
                    playbook_version_id=playbook_version_id,
                    actor=actor,
                    event_type=event_type.value,
                    correlation_id=correlation_id,
                    row_version_after=row_version_after,
                    metadata=payload,
                )
            )
        except IntegrityError as exc:
            raise PlaybookValidationError(
                f"playbook audit insert rejected: {exc.orig if exc.orig is not None else exc}"
            ) from exc
        row = (
            connection.execute(
                select(playbook_audit_events).where(playbook_audit_events.c.event_id == event_id)
            )
            .mappings()
            .one()
        )
        return self._audit_record(row)

    def insert_evaluation(
        self,
        connection: Connection,
        *,
        evaluation_id: UUID,
        matter_id: UUID,
        occurred_at: datetime,
        actor: str,
        outcome_code: EvaluationOutcome,
        reason_code: EvaluationReason,
        selected_playbook_version_id: UUID | None,
        matter_row_version_observed: int,
        notes: str | None,
        correlation_id: UUID | None,
        candidates: list[tuple[UUID, int, RuleResult]],
    ) -> EvaluationRecord:
        try:
            connection.execute(
                insert(casework_playbook_evaluations).values(
                    evaluation_id=evaluation_id,
                    matter_id=matter_id,
                    occurred_at=occurred_at,
                    actor=actor,
                    outcome_code=outcome_code.value,
                    reason_code=reason_code.value,
                    selected_playbook_version_id=selected_playbook_version_id,
                    matter_row_version_observed=matter_row_version_observed,
                    notes=notes,
                    correlation_id=correlation_id,
                )
            )
            for version_id, order, eligibility in candidates:
                if eligibility not in {RuleResult.MATCH, RuleResult.UNKNOWN}:
                    raise PlaybookValidationError(
                        "evaluation candidates may only store MATCH or UNKNOWN"
                    )
                connection.execute(
                    insert(casework_playbook_evaluation_candidates).values(
                        evaluation_id=evaluation_id,
                        playbook_version_id=version_id,
                        presentation_order=order,
                        eligibility_result=eligibility.value,
                    )
                )
        except IntegrityError as exc:
            raise PlaybookValidationError(
                f"evaluation insert rejected: {exc.orig if exc.orig is not None else exc}"
            ) from exc
        return EvaluationRecord(
            evaluation_id=evaluation_id,
            matter_id=matter_id,
            occurred_at=occurred_at,
            actor=actor,
            outcome_code=outcome_code,
            reason_code=reason_code,
            selected_playbook_version_id=selected_playbook_version_id,
            matter_row_version_observed=matter_row_version_observed,
            notes=notes,
            correlation_id=correlation_id,
        )

    def list_intake_answers(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        playbook_version_id: UUID,
    ) -> list[IntakeAnswerRecord]:
        rows = (
            connection.execute(
                select(casework_intake_answers).where(
                    casework_intake_answers.c.matter_id == matter_id,
                    casework_intake_answers.c.playbook_version_id == playbook_version_id,
                )
            )
            .mappings()
            .all()
        )
        return [self._intake_record(row) for row in rows]

    def list_checklist_states(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        playbook_version_id: UUID,
    ) -> list[ChecklistStateRecord]:
        rows = (
            connection.execute(
                select(casework_checklist_states).where(
                    casework_checklist_states.c.matter_id == matter_id,
                    casework_checklist_states.c.playbook_version_id == playbook_version_id,
                )
            )
            .mappings()
            .all()
        )
        return [self._checklist_record(row) for row in rows]

    def snapshot_intake_to_history(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        playbook_version_id: UUID,
        superseded_at: datetime,
        superseded_by: str,
        superseded_by_playbook_version_id: UUID,
        upgrade_correlation_id: UUID,
    ) -> int:
        answers = self.list_intake_answers(
            connection, matter_id=matter_id, playbook_version_id=playbook_version_id
        )
        for answer in answers:
            connection.execute(
                insert(casework_intake_answers_history).values(
                    history_id=uuid4(),
                    matter_id=answer.matter_id,
                    playbook_version_id=answer.playbook_version_id,
                    question_id=answer.question_id,
                    value_type=answer.value_type.value,
                    value_boolean=answer.value_boolean,
                    value_text=answer.value_text,
                    value_date=answer.value_date,
                    value_enum_code=answer.value_enum_code,
                    answered_by=answer.answered_by,
                    answered_at=answer.answered_at,
                    row_version=answer.row_version,
                    superseded_at=superseded_at,
                    superseded_by=superseded_by,
                    superseded_by_playbook_version_id=superseded_by_playbook_version_id,
                    upgrade_correlation_id=upgrade_correlation_id,
                )
            )
        return len(answers)

    def snapshot_checklist_to_history(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        playbook_version_id: UUID,
        superseded_at: datetime,
        superseded_by: str,
        superseded_by_playbook_version_id: UUID,
        upgrade_correlation_id: UUID,
    ) -> int:
        states = self.list_checklist_states(
            connection, matter_id=matter_id, playbook_version_id=playbook_version_id
        )
        for state in states:
            connection.execute(
                insert(casework_checklist_states_history).values(
                    history_id=uuid4(),
                    matter_id=state.matter_id,
                    playbook_version_id=state.playbook_version_id,
                    checklist_item_id=state.checklist_item_id,
                    status=state.status.value,
                    note=state.note,
                    updated_by=state.updated_by,
                    updated_at=state.updated_at,
                    row_version=state.row_version,
                    superseded_at=superseded_at,
                    superseded_by=superseded_by,
                    superseded_by_playbook_version_id=superseded_by_playbook_version_id,
                    upgrade_correlation_id=upgrade_correlation_id,
                )
            )
        return len(states)

    def delete_live_intake_and_checklist(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        playbook_version_id: UUID,
    ) -> None:
        connection.execute(
            delete(casework_intake_answers).where(
                casework_intake_answers.c.matter_id == matter_id,
                casework_intake_answers.c.playbook_version_id == playbook_version_id,
            )
        )
        connection.execute(
            delete(casework_checklist_states).where(
                casework_checklist_states.c.matter_id == matter_id,
                casework_checklist_states.c.playbook_version_id == playbook_version_id,
            )
        )

    def upsert_intake_answer(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        playbook_version_id: UUID,
        question_id: str,
        value_type: IntakeValueType,
        value_boolean: bool | None,
        value_text: str | None,
        value_date: date | None,
        value_enum_code: str | None,
        answered_by: str,
        answered_at: datetime,
        expected_row_version: int | None,
    ) -> IntakeAnswerRecord:
        existing = (
            connection.execute(
                select(casework_intake_answers).where(
                    casework_intake_answers.c.matter_id == matter_id,
                    casework_intake_answers.c.playbook_version_id == playbook_version_id,
                    casework_intake_answers.c.question_id == question_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is None:
            if expected_row_version is not None:
                raise ConcurrencyConflictError(
                    "intake answer does not exist; expected_row_version must be None"
                )
            try:
                connection.execute(
                    insert(casework_intake_answers).values(
                        matter_id=matter_id,
                        playbook_version_id=playbook_version_id,
                        question_id=question_id,
                        value_type=value_type.value,
                        value_boolean=value_boolean,
                        value_text=value_text,
                        value_date=value_date,
                        value_enum_code=value_enum_code,
                        answered_by=answered_by,
                        answered_at=answered_at,
                        row_version=1,
                    )
                )
            except IntegrityError as exc:
                raise ConcurrencyConflictError(
                    "intake answer create conflict; row now exists or pin changed"
                ) from exc
        else:
            current_version = cast(int, existing["row_version"])
            if expected_row_version is None:
                raise ConcurrencyConflictError(
                    "intake answer exists; expected_row_version is required for update"
                )
            if expected_row_version != current_version:
                raise ConcurrencyConflictError(
                    f"intake answer row_version conflict at {expected_row_version}"
                )
            result = connection.execute(
                update(casework_intake_answers)
                .where(
                    casework_intake_answers.c.matter_id == matter_id,
                    casework_intake_answers.c.playbook_version_id == playbook_version_id,
                    casework_intake_answers.c.question_id == question_id,
                    casework_intake_answers.c.row_version == current_version,
                )
                .values(
                    value_type=value_type.value,
                    value_boolean=value_boolean,
                    value_text=value_text,
                    value_date=value_date,
                    value_enum_code=value_enum_code,
                    answered_by=answered_by,
                    answered_at=answered_at,
                    row_version=current_version + 1,
                )
            )
            if result.rowcount != 1:
                raise ConcurrencyConflictError(
                    f"intake answer row_version conflict at {current_version}"
                )
        row = (
            connection.execute(
                select(casework_intake_answers).where(
                    casework_intake_answers.c.matter_id == matter_id,
                    casework_intake_answers.c.playbook_version_id == playbook_version_id,
                    casework_intake_answers.c.question_id == question_id,
                )
            )
            .mappings()
            .one()
        )
        return self._intake_record(row)

    def upsert_checklist_state(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        playbook_version_id: UUID,
        checklist_item_id: str,
        status: ChecklistItemStatus,
        note: str | None,
        updated_by: str,
        updated_at: datetime,
        expected_row_version: int | None,
    ) -> ChecklistStateRecord:
        existing = (
            connection.execute(
                select(casework_checklist_states).where(
                    casework_checklist_states.c.matter_id == matter_id,
                    casework_checklist_states.c.playbook_version_id == playbook_version_id,
                    casework_checklist_states.c.checklist_item_id == checklist_item_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is None:
            if expected_row_version is not None:
                raise ConcurrencyConflictError(
                    "checklist state does not exist; expected_row_version must be None"
                )
            try:
                connection.execute(
                    insert(casework_checklist_states).values(
                        matter_id=matter_id,
                        playbook_version_id=playbook_version_id,
                        checklist_item_id=checklist_item_id,
                        status=status.value,
                        note=note,
                        updated_by=updated_by,
                        updated_at=updated_at,
                        row_version=1,
                    )
                )
            except IntegrityError as exc:
                raise ConcurrencyConflictError(
                    "checklist state create conflict; row now exists or pin changed"
                ) from exc
        else:
            current_version = cast(int, existing["row_version"])
            if expected_row_version is None:
                raise ConcurrencyConflictError(
                    "checklist state exists; expected_row_version is required for update"
                )
            if expected_row_version != current_version:
                raise ConcurrencyConflictError(
                    f"checklist state row_version conflict at {expected_row_version}"
                )
            result = connection.execute(
                update(casework_checklist_states)
                .where(
                    casework_checklist_states.c.matter_id == matter_id,
                    casework_checklist_states.c.playbook_version_id == playbook_version_id,
                    casework_checklist_states.c.checklist_item_id == checklist_item_id,
                    casework_checklist_states.c.row_version == current_version,
                )
                .values(
                    status=status.value,
                    note=note,
                    updated_by=updated_by,
                    updated_at=updated_at,
                    row_version=current_version + 1,
                )
            )
            if result.rowcount != 1:
                raise ConcurrencyConflictError(
                    f"checklist state row_version conflict at {current_version}"
                )
        row = (
            connection.execute(
                select(casework_checklist_states).where(
                    casework_checklist_states.c.matter_id == matter_id,
                    casework_checklist_states.c.playbook_version_id == playbook_version_id,
                    casework_checklist_states.c.checklist_item_id == checklist_item_id,
                )
            )
            .mappings()
            .one()
        )
        return self._checklist_record(row)

    @staticmethod
    def _version_record(row: RowMapping) -> PlaybookVersionRecord:
        return PlaybookVersionRecord(
            playbook_version_id=cast(UUID, row["playbook_version_id"]),
            playbook_key=cast(str, row["playbook_key"]),
            version=cast(int, row["version"]),
            status=PlaybookStatus(cast(str, row["status"])),
            schema_version=cast(int, row["schema_version"]),
            definition_json=dict(cast(dict[str, Any], row["definition_json"])),
            content_sha256=cast(str, row["content_sha256"]),
            row_version=cast(int, row["row_version"]),
            created_by=cast(str, row["created_by"]),
            created_at=cast(datetime, row["created_at"]),
            updated_by=cast(str, row["updated_by"]),
            updated_at=cast(datetime, row["updated_at"]),
            activated_by=cast(str | None, row["activated_by"]),
            activated_at=cast(datetime | None, row["activated_at"]),
            effective_from=cast(datetime | None, row["effective_from"]),
            retired_by=cast(str | None, row["retired_by"]),
            retired_at=cast(datetime | None, row["retired_at"]),
            retirement_reason_code=cast(str | None, row["retirement_reason_code"]),
        )

    @staticmethod
    def _audit_record(row: RowMapping) -> PlaybookAuditEventRecord:
        return PlaybookAuditEventRecord(
            event_id=cast(UUID, row["event_id"]),
            playbook_key=cast(str, row["playbook_key"]),
            version=cast(int, row["version"]),
            playbook_version_id=cast(UUID, row["playbook_version_id"]),
            actor=cast(str, row["actor"]),
            event_type=PlaybookAuditEventType(cast(str, row["event_type"])),
            occurred_at=cast(datetime, row["occurred_at"]),
            correlation_id=cast(UUID | None, row["correlation_id"]),
            row_version_after=cast(int | None, row["row_version_after"]),
            metadata=dict(cast(dict[str, Any], row["metadata"])),
        )

    @staticmethod
    def _intake_record(row: RowMapping) -> IntakeAnswerRecord:
        return IntakeAnswerRecord(
            matter_id=cast(UUID, row["matter_id"]),
            playbook_version_id=cast(UUID, row["playbook_version_id"]),
            question_id=cast(str, row["question_id"]),
            value_type=IntakeValueType(cast(str, row["value_type"])),
            value_boolean=cast(bool | None, row["value_boolean"]),
            value_text=cast(str | None, row["value_text"]),
            value_date=cast(date | None, row["value_date"]),
            value_enum_code=cast(str | None, row["value_enum_code"]),
            answered_by=cast(str, row["answered_by"]),
            answered_at=cast(datetime, row["answered_at"]),
            row_version=cast(int, row["row_version"]),
        )

    @staticmethod
    def _checklist_record(row: RowMapping) -> ChecklistStateRecord:
        return ChecklistStateRecord(
            matter_id=cast(UUID, row["matter_id"]),
            playbook_version_id=cast(UUID, row["playbook_version_id"]),
            checklist_item_id=cast(str, row["checklist_item_id"]),
            status=ChecklistItemStatus(cast(str, row["status"])),
            note=cast(str | None, row["note"]),
            updated_by=cast(str, row["updated_by"]),
            updated_at=cast(datetime, row["updated_at"]),
            row_version=cast(int, row["row_version"]),
        )


# Re-export for callers that expect NotFoundError from playbook package paths.
__all__ = ["PlaybookRepository", "NotFoundError"]

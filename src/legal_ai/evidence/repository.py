"""Database-only, matter-scoped evidence persistence."""

# ruff: noqa: E501

from __future__ import annotations

import builtins
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Connection, Engine, RowMapping, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from legal_ai.casework.repository import CaseworkRepository
from legal_ai.db import (
    casework_evidence_checklist_links,
    casework_evidence_derivations,
    casework_evidence_records,
    playbook_versions,
)

from .errors import (
    ChecklistLinkConflict,
    ChecklistLinkPersistenceError,
    EvidenceNotFound,
    EvidenceProvenanceConflict,
    InvalidChecklistAssociation,
    InvalidReviewTransition,
    TerminalReviewMutationDenied,
)
from .models import EvidenceChecklistLink, EvidenceDerivation, EvidenceRecord
from .types import EvidenceKind, EvidenceReviewStatus, EvidenceRole


class EvidenceRepository:
    def __init__(self, bind: Engine | Connection) -> None:
        self._bind = bind
        self.casework = CaseworkRepository(bind)

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        with self.casework.transaction() as connection:
            yield connection

    @contextmanager
    def independent_transaction(self) -> Iterator[Connection]:
        with self.casework.independent_transaction() as connection:
            yield connection

    def get(
        self, connection: Connection, *, matter_id: UUID, evidence_id: UUID
    ) -> EvidenceRecord | None:
        row = (
            connection.execute(
                select(casework_evidence_records).where(
                    casework_evidence_records.c.matter_id == matter_id,
                    casework_evidence_records.c.evidence_id == evidence_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else self._record(row)

    def require(
        self, connection: Connection, *, matter_id: UUID, evidence_id: UUID
    ) -> EvidenceRecord:
        record = self.get(connection, matter_id=matter_id, evidence_id=evidence_id)
        if record is None:
            raise EvidenceNotFound("evidence not found in matter")
        return record

    def list(self, connection: Connection, *, matter_id: UUID) -> builtins.list[EvidenceRecord]:
        rows = connection.execute(
            select(casework_evidence_records)
            .where(casework_evidence_records.c.matter_id == matter_id)
            .order_by(
                casework_evidence_records.c.registered_at, casework_evidence_records.c.evidence_id
            )
        ).mappings()
        return [self._record(row) for row in rows]

    def register(
        self,
        connection: Connection,
        *,
        evidence_id: UUID,
        matter_id: UUID,
        artifact_sha256: str,
        evidence_kind: EvidenceKind,
        evidence_role: EvidenceRole,
        caller_filename: str,
        declared_media_type: str,
        detected_media_type: str,
        expected_byte_size: int,
        supplied_metadata: Mapping[str, object],
        actor: str,
    ) -> tuple[EvidenceRecord, bool]:
        existing = (
            connection.execute(
                select(casework_evidence_records).where(
                    casework_evidence_records.c.matter_id == matter_id,
                    casework_evidence_records.c.artifact_sha256 == artifact_sha256,
                )
            )
            .mappings()
            .one_or_none()
        )
        submitted = {
            "matter_id": matter_id,
            "artifact_sha256": artifact_sha256,
            "evidence_kind": evidence_kind.value,
            "evidence_role": evidence_role.value,
            "caller_filename": caller_filename,
            "declared_media_type": declared_media_type,
            "detected_media_type": detected_media_type,
            "expected_byte_size": expected_byte_size,
            "supplied_unverified_metadata": dict(supplied_metadata),
        }
        inserted = False
        if existing is None:
            try:
                returned_id = connection.execute(
                    insert(casework_evidence_records)
                    .values(evidence_id=evidence_id, registered_by=actor, **submitted)
                    .on_conflict_do_nothing(constraint="uq_evidence_records_matter_artifact")
                    .returning(casework_evidence_records.c.evidence_id)
                ).scalar_one_or_none()
                inserted = returned_id == evidence_id
            except IntegrityError as exc:
                raise EvidenceProvenanceConflict(
                    "evidence registration violated provenance constraints"
                ) from exc
            existing = (
                connection.execute(
                    select(casework_evidence_records).where(
                        casework_evidence_records.c.matter_id == matter_id,
                        casework_evidence_records.c.artifact_sha256 == artifact_sha256,
                    )
                )
                .mappings()
                .one()
            )
        conflicts = [key for key, value in submitted.items() if existing[key] != value]
        if conflicts:
            raise EvidenceProvenanceConflict(
                f"evidence metadata conflicts on {', '.join(sorted(conflicts))}"
            )
        return self._record(existing), not inserted

    def insert_derivation(
        self, connection: Connection, derivation: EvidenceDerivation
    ) -> EvidenceDerivation:
        try:
            connection.execute(
                insert(casework_evidence_derivations).values(
                    **{
                        "derivation_id": derivation.derivation_id,
                        "matter_id": derivation.matter_id,
                        "source_evidence_id": derivation.source_evidence_id,
                        "source_artifact_sha256": derivation.source_artifact_sha256,
                        "derived_evidence_id": derivation.derived_evidence_id,
                        "derived_artifact_sha256": derivation.derived_artifact_sha256,
                        "operation_code": derivation.operation_code,
                        "operation_version": derivation.operation_version,
                        "processor_version": derivation.processor_version,
                        "parameters_sha256": derivation.parameters_sha256,
                        "deterministic": derivation.deterministic,
                        "created_by": derivation.created_by,
                        "created_at": derivation.created_at,
                    }
                )
            )
        except IntegrityError as exc:
            raise EvidenceProvenanceConflict("derivation violated provenance constraints") from exc
        return derivation

    def get_derivation(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        derived_evidence_id: UUID,
    ) -> EvidenceDerivation | None:
        row = (
            connection.execute(
                select(casework_evidence_derivations).where(
                    casework_evidence_derivations.c.matter_id == matter_id,
                    casework_evidence_derivations.c.derived_evidence_id == derived_evidence_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else self._derivation(row)

    def ancestry(
        self, connection: Connection, *, matter_id: UUID, evidence_id: UUID
    ) -> builtins.list[EvidenceDerivation]:
        self.require(connection, matter_id=matter_id, evidence_id=evidence_id)
        rows = connection.exec_driver_sql(
            """WITH RECURSIVE ancestry AS (SELECT d.*, 1 depth FROM casework_evidence_derivations d WHERE d.matter_id=%(matter_id)s AND d.derived_evidence_id=%(evidence_id)s UNION ALL SELECT d.*, a.depth+1 FROM casework_evidence_derivations d JOIN ancestry a ON d.matter_id=a.matter_id AND d.derived_evidence_id=a.source_evidence_id) SELECT * FROM ancestry ORDER BY depth""",
            {"matter_id": matter_id, "evidence_id": evidence_id},
        ).mappings()
        return [self._derivation(row) for row in rows]

    def review(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        evidence_id: UUID,
        expected_row_version: int,
        status: EvidenceReviewStatus,
        reviewer: str,
        reviewed_at: datetime,
        reason: str,
    ) -> EvidenceRecord:
        result = connection.execute(
            update(casework_evidence_records)
            .where(
                casework_evidence_records.c.matter_id == matter_id,
                casework_evidence_records.c.evidence_id == evidence_id,
                casework_evidence_records.c.row_version == expected_row_version,
                casework_evidence_records.c.review_status == EvidenceReviewStatus.UPLOADED.value,
            )
            .values(
                review_status=status.value,
                reviewed_by=reviewer,
                reviewed_at=reviewed_at,
                review_reason=reason,
                row_version=expected_row_version + 1,
            )
        )
        if result.rowcount != 1:
            record = self.get(connection, matter_id=matter_id, evidence_id=evidence_id)
            if record is None:
                raise EvidenceNotFound("evidence not found in matter")
            if record.review_status is not EvidenceReviewStatus.UPLOADED:
                raise TerminalReviewMutationDenied("evidence review status is already terminal")
            raise InvalidReviewTransition("review transition is stale or invalid")
        return self.require(connection, matter_id=matter_id, evidence_id=evidence_id)

    def definition_has_item(
        self, connection: Connection, *, playbook_version_id: UUID, checklist_item_id: str
    ) -> bool:
        definition = connection.execute(
            select(playbook_versions.c.definition_json).where(
                playbook_versions.c.playbook_version_id == playbook_version_id
            )
        ).scalar_one_or_none()
        return isinstance(definition, dict) and any(
            isinstance(item, dict) and item.get("checklist_item_id") == checklist_item_id
            for item in definition.get("evidence_checklist", [])
        )

    def link_checklist(
        self, connection: Connection, link: EvidenceChecklistLink
    ) -> tuple[EvidenceChecklistLink, bool]:
        try:
            returned_id = connection.execute(
                insert(casework_evidence_checklist_links)
                .values(
                    matter_id=link.matter_id,
                    evidence_id=link.evidence_id,
                    playbook_version_id=link.playbook_version_id,
                    checklist_item_id=link.checklist_item_id,
                    linked_by=link.linked_by,
                    linked_at=link.linked_at,
                )
                .on_conflict_do_nothing(constraint="pk_casework_evidence_checklist_links")
                .returning(casework_evidence_checklist_links.c.matter_id)
            ).scalar_one_or_none()
            if returned_id is not None:
                return self._require_checklist_link(
                    connection,
                    matter_id=link.matter_id,
                    evidence_id=link.evidence_id,
                    playbook_version_id=link.playbook_version_id,
                    checklist_item_id=link.checklist_item_id,
                ), True
            stored_row = self._get_checklist_link(
                connection,
                matter_id=link.matter_id,
                evidence_id=link.evidence_id,
                playbook_version_id=link.playbook_version_id,
                checklist_item_id=link.checklist_item_id,
            )
            if stored_row is None:
                raise ChecklistLinkPersistenceError("checklist link not found after insertion")
            if (
                stored_row.matter_id != link.matter_id
                or stored_row.evidence_id != link.evidence_id
                or stored_row.playbook_version_id != link.playbook_version_id
                or stored_row.checklist_item_id != link.checklist_item_id
                or stored_row.linked_by != link.linked_by
                or stored_row.linked_at != link.linked_at
            ):
                raise ChecklistLinkConflict(
                    "existing checklist link has conflicting immutable metadata"
                )
            return stored_row, False
        except IntegrityError as exc:
            raise InvalidChecklistAssociation(
                "checklist association violates the authoritative pin"
            ) from exc

    def _get_checklist_link(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        evidence_id: UUID,
        playbook_version_id: UUID,
        checklist_item_id: str,
    ) -> EvidenceChecklistLink | None:
        row = (
            connection.execute(
                select(casework_evidence_checklist_links).where(
                    casework_evidence_checklist_links.c.matter_id == matter_id,
                    casework_evidence_checklist_links.c.evidence_id == evidence_id,
                    casework_evidence_checklist_links.c.playbook_version_id == playbook_version_id,
                    casework_evidence_checklist_links.c.checklist_item_id == checklist_item_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else self._checklist_link(row)

    def _require_checklist_link(
        self,
        connection: Connection,
        *,
        matter_id: UUID,
        evidence_id: UUID,
        playbook_version_id: UUID,
        checklist_item_id: str,
    ) -> EvidenceChecklistLink:
        link = self._get_checklist_link(
            connection,
            matter_id=matter_id,
            evidence_id=evidence_id,
            playbook_version_id=playbook_version_id,
            checklist_item_id=checklist_item_id,
        )
        if link is None:
            raise ChecklistLinkPersistenceError("checklist link not found after insert")
        return link

    @staticmethod
    def _checklist_link(row: RowMapping) -> EvidenceChecklistLink:
        return EvidenceChecklistLink(
            matter_id=cast(UUID, row["matter_id"]),
            evidence_id=cast(UUID, row["evidence_id"]),
            playbook_version_id=cast(UUID, row["playbook_version_id"]),
            checklist_item_id=cast(str, row["checklist_item_id"]),
            linked_by=cast(str, row["linked_by"]),
            linked_at=cast(datetime, row["linked_at"]),
        )

    @staticmethod
    def _record(row: RowMapping) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=cast(UUID, row["evidence_id"]),
            matter_id=cast(UUID, row["matter_id"]),
            artifact_sha256=cast(str, row["artifact_sha256"]),
            evidence_kind=EvidenceKind(cast(str, row["evidence_kind"])),
            evidence_role=EvidenceRole(cast(str, row["evidence_role"])),
            caller_filename=cast(str, row["caller_filename"]),
            declared_media_type=cast(str, row["declared_media_type"]),
            detected_media_type=cast(str, row["detected_media_type"]),
            expected_byte_size=cast(int, row["expected_byte_size"]),
            supplied_unverified_metadata=cast(
                dict[str, object], row["supplied_unverified_metadata"]
            ),
            review_status=EvidenceReviewStatus(cast(str, row["review_status"])),
            row_version=cast(int, row["row_version"]),
            registered_by=cast(str, row["registered_by"]),
            registered_at=cast(datetime, row["registered_at"]),
            reviewed_by=cast(str | None, row["reviewed_by"]),
            reviewed_at=cast(datetime | None, row["reviewed_at"]),
            review_reason=cast(str | None, row["review_reason"]),
        )

    @staticmethod
    def _derivation(row: RowMapping) -> EvidenceDerivation:
        return EvidenceDerivation(
            **{key: row[key] for key in EvidenceDerivation.__dataclass_fields__}
        )

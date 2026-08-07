"""Fail-closed application service for matter-scoped evidence."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Connection

from legal_ai.casework.models import MatterRecord
from legal_ai.casework.types import (
    ActionAuthorityLevel,
    AuditEventType,
    MatterStatus,
    authority_rank,
)
from legal_ai.provenance import ArtifactRegistry, LocalArtifactStore
from legal_ai.provenance.content_store import ArtifactContent
from legal_ai.provenance.errors import ArtifactStoreError, ProvenanceIntegrityConflict

from .errors import (
    ChecklistLinkConflict,
    ClosedMatterEvidenceWriteDenied,
    CrossMatterEvidenceDenied,
    DeclaredMediaTypeMismatch,
    EmptyEvidenceInput,
    EvidenceAuditWriteFailed,
    EvidenceAuthorityDenied,
    EvidenceNotFound,
    EvidenceProvenanceConflict,
    EvidenceSizeLimitExceeded,
    EvidenceStorageFailure,
    ExpectedSizeMismatch,
    ExtensionMismatch,
    InvalidChecklistAssociation,
    MalformedSignature,
    SameContentDerivation,
    TerminalReviewMutationDenied,
    TruncatedEvidenceStream,
    UnsafeFilename,
    UnsupportedFileType,
)
from .models import (
    EvidenceChecklistLink,
    EvidenceDerivation,
    EvidenceRecord,
    LinkEvidenceChecklistCommand,
    ReadEvidenceCommand,
    RegisterDerivedEvidenceCommand,
    ReviewEvidenceCommand,
    UploadEvidenceCommand,
)
from .repository import EvidenceRepository
from .signatures import ValidatedEvidenceStream
from .types import EvidenceRejectionCode, EvidenceRole

_REJECTION_CODES = {
    UnsupportedFileType: EvidenceRejectionCode.TYPE_NOT_ALLOWED,
    MalformedSignature: EvidenceRejectionCode.SIGNATURE_MALFORMED,
    DeclaredMediaTypeMismatch: EvidenceRejectionCode.DECLARED_TYPE_MISMATCH,
    ExtensionMismatch: EvidenceRejectionCode.EXTENSION_MISMATCH,
    EmptyEvidenceInput: EvidenceRejectionCode.EMPTY_INPUT,
    EvidenceSizeLimitExceeded: EvidenceRejectionCode.SIZE_LIMIT_EXCEEDED,
    UnsafeFilename: EvidenceRejectionCode.UNSAFE_FILENAME,
    ExpectedSizeMismatch: EvidenceRejectionCode.EXPECTED_SIZE_MISMATCH,
    TruncatedEvidenceStream: EvidenceRejectionCode.TRUNCATED_STREAM,
}


class EvidenceService:
    def __init__(self, repository: EvidenceRepository, artifact_store: LocalArtifactStore) -> None:
        self._repo = repository
        self._store = artifact_store
        self._registry = ArtifactRegistry()

    def upload(self, command: UploadEvidenceCommand, content: ArtifactContent) -> EvidenceRecord:
        evidence_id = uuid4()
        self._authorize_write(
            command.matter_id,
            command.actor,
            command.source_channel,
            command.correlation_id,
            "UPLOAD",
        )
        stream = ValidatedEvidenceStream(
            content,
            filename=command.caller_filename,
            declared_media_type=command.declared_media_type,
            expected_byte_size=command.expected_byte_size,
        )
        try:
            artifact = self._store.store(stream, max_bytes=command.expected_byte_size)
        except tuple(_REJECTION_CODES) as exc:
            self._audit_rejection(command, evidence_id, _REJECTION_CODES[type(exc)])
            raise
        except ArtifactStoreError as exc:
            raise EvidenceStorageFailure("evidence storage failed closed") from exc
        assert stream.result is not None
        try:
            with self._repo.transaction() as connection:
                matter = self._repo.casework.lock_matter(connection, command.matter_id)
                self._require_l1_open(matter)
                self._registry.register(
                    connection, artifact, media_type=stream.result.canonical_media_type
                )
                record, reused = self._repo.register(
                    connection,
                    evidence_id=evidence_id,
                    matter_id=command.matter_id,
                    artifact_sha256=artifact.sha256,
                    evidence_kind=stream.result.kind,
                    evidence_role=EvidenceRole.ORIGINAL,
                    caller_filename=stream.result.normalized_filename,
                    declared_media_type=command.declared_media_type,
                    detected_media_type=stream.result.canonical_media_type,
                    expected_byte_size=command.expected_byte_size,
                    supplied_metadata=self._metadata(command),
                    actor=command.actor,
                )
                self._audit(
                    connection,
                    command.matter_id,
                    command.actor,
                    AuditEventType.EVIDENCE_DUPLICATE_REUSED
                    if reused
                    else AuditEventType.EVIDENCE_REGISTERED,
                    record.evidence_id,
                    command.source_channel,
                    command.correlation_id,
                    {
                        "artifact_sha256": artifact.sha256,
                        "evidence_kind": record.evidence_kind.value,
                        "evidence_role": record.evidence_role.value,
                        "detected_media_type": record.detected_media_type,
                        "expected_byte_size": record.expected_byte_size,
                    },
                )
                self._audit(
                    connection,
                    command.matter_id,
                    command.actor,
                    AuditEventType.EVIDENCE_UPLOAD_ACCEPTED,
                    record.evidence_id,
                    command.source_channel,
                    command.correlation_id,
                    {
                        "artifact_sha256": artifact.sha256,
                        "declared_media_type": command.declared_media_type,
                        "detected_media_type": record.detected_media_type,
                        "expected_byte_size": record.expected_byte_size,
                    },
                )
                return record
        except (EvidenceProvenanceConflict, ProvenanceIntegrityConflict) as exc:
            self._audit_independent(
                command.matter_id,
                command.actor,
                AuditEventType.EVIDENCE_PROVENANCE_CONFLICT,
                evidence_id,
                command.source_channel,
                command.correlation_id,
                "PROVENANCE_CONFLICT",
                {"artifact_sha256": artifact.sha256, "reason_code": "PROVENANCE_CONFLICT"},
            )
            raise EvidenceProvenanceConflict(
                "evidence provenance conflicts with authoritative metadata"
            ) from exc
        except (ClosedMatterEvidenceWriteDenied, EvidenceAuthorityDenied) as exc:
            self._audit_denial(
                command.matter_id,
                command.actor,
                command.source_channel,
                command.correlation_id,
                evidence_id,
                "CLOSED_MATTER"
                if isinstance(exc, ClosedMatterEvidenceWriteDenied)
                else "AUTHORITY_DENIED",
                "UPLOAD",
            )
            raise

    def register_derived(
        self, command: RegisterDerivedEvidenceCommand, content: ArtifactContent
    ) -> EvidenceRecord:
        self._authorize_write(
            command.matter_id,
            command.actor,
            command.source_channel,
            command.correlation_id,
            "DERIVE",
        )
        with self._repo.transaction() as connection:
            source = self._repo.get(
                connection, matter_id=command.matter_id, evidence_id=command.source_evidence_id
            )
        if source is None:
            self._audit_denial(
                command.matter_id,
                command.actor,
                command.source_channel,
                command.correlation_id,
                command.source_evidence_id,
                "CROSS_MATTER_OR_MISSING_SOURCE",
                "DERIVE",
            )
            raise CrossMatterEvidenceDenied("derivation source is unavailable in the matter")
        stream = ValidatedEvidenceStream(
            content,
            filename=command.caller_filename,
            declared_media_type=command.declared_media_type,
            expected_byte_size=command.expected_byte_size,
        )
        try:
            artifact = self._store.store(stream, max_bytes=command.expected_byte_size)
        except tuple(_REJECTION_CODES) as exc:
            self._audit_rejection(command, uuid4(), _REJECTION_CODES[type(exc)])
            raise
        except ArtifactStoreError as exc:
            raise EvidenceStorageFailure("evidence storage failed closed") from exc
        if artifact.sha256 == source.artifact_sha256:
            self._audit_independent(
                command.matter_id,
                command.actor,
                AuditEventType.EVIDENCE_PROVENANCE_CONFLICT,
                source.evidence_id,
                command.source_channel,
                command.correlation_id,
                "SAME_CONTENT_DERIVATION",
                {
                    "source_evidence_id": str(source.evidence_id),
                    "artifact_sha256": artifact.sha256,
                    "reason_code": "SAME_CONTENT_DERIVATION",
                },
            )
            raise SameContentDerivation("derived evidence must have distinct content")
        assert stream.result is not None
        evidence_id, now = uuid4(), datetime.now(UTC)
        with (
            self._provenance_conflict_boundary(command, evidence_id, artifact.sha256),
            self._repo.transaction() as connection,
        ):
            matter = self._repo.casework.lock_matter(connection, command.matter_id)
            self._require_l1_open(matter)
            source = self._repo.require(
                connection, matter_id=command.matter_id, evidence_id=command.source_evidence_id
            )
            self._registry.register(
                connection, artifact, media_type=stream.result.canonical_media_type
            )
            record, reused = self._repo.register(
                connection,
                evidence_id=evidence_id,
                matter_id=command.matter_id,
                artifact_sha256=artifact.sha256,
                evidence_kind=stream.result.kind,
                evidence_role=EvidenceRole.DERIVED,
                caller_filename=stream.result.normalized_filename,
                declared_media_type=command.declared_media_type,
                detected_media_type=stream.result.canonical_media_type,
                expected_byte_size=command.expected_byte_size,
                supplied_metadata=self._metadata(command),
                actor=command.actor,
            )
            if reused:
                if record.evidence_role is not EvidenceRole.DERIVED:
                    raise EvidenceProvenanceConflict("existing same-matter evidence is not derived")
                existing_derivation = self._repo.get_derivation(
                    connection,
                    matter_id=command.matter_id,
                    derived_evidence_id=record.evidence_id,
                )
                expected = (
                    source.evidence_id,
                    command.operation_code,
                    command.operation_version,
                    command.processor_version,
                    command.parameters_sha256,
                    command.deterministic,
                )
                actual = (
                    None
                    if existing_derivation is None
                    else (
                        existing_derivation.source_evidence_id,
                        existing_derivation.operation_code,
                        existing_derivation.operation_version,
                        existing_derivation.processor_version,
                        existing_derivation.parameters_sha256,
                        existing_derivation.deterministic,
                    )
                )
                if actual != expected:
                    raise EvidenceProvenanceConflict(
                        "existing derived evidence has conflicting provenance"
                    )
            else:
                derivation = EvidenceDerivation(
                    derivation_id=uuid4(),
                    matter_id=command.matter_id,
                    source_evidence_id=source.evidence_id,
                    source_artifact_sha256=source.artifact_sha256,
                    derived_evidence_id=record.evidence_id,
                    derived_artifact_sha256=record.artifact_sha256,
                    operation_code=command.operation_code,
                    operation_version=command.operation_version,
                    processor_version=command.processor_version,
                    parameters_sha256=command.parameters_sha256,
                    deterministic=command.deterministic,
                    created_by=command.actor,
                    created_at=now,
                )
                self._repo.insert_derivation(connection, derivation)
                self._audit(
                    connection,
                    command.matter_id,
                    command.actor,
                    AuditEventType.EVIDENCE_DERIVATION_REGISTERED,
                    record.evidence_id,
                    command.source_channel,
                    command.correlation_id,
                    {
                        "source_evidence_id": str(source.evidence_id),
                        "artifact_sha256": record.artifact_sha256,
                        "operation_code": command.operation_code,
                        "operation_version": command.operation_version,
                        "processor_version": command.processor_version,
                        "parameters_sha256": command.parameters_sha256,
                        "deterministic": command.deterministic,
                    },
                )
            self._audit(
                connection,
                command.matter_id,
                command.actor,
                AuditEventType.EVIDENCE_DUPLICATE_REUSED
                if reused
                else AuditEventType.EVIDENCE_REGISTERED,
                record.evidence_id,
                command.source_channel,
                command.correlation_id,
                {
                    "artifact_sha256": record.artifact_sha256,
                    "evidence_kind": record.evidence_kind.value,
                    "evidence_role": record.evidence_role.value,
                },
            )
            self._audit(
                connection,
                command.matter_id,
                command.actor,
                AuditEventType.EVIDENCE_UPLOAD_ACCEPTED,
                record.evidence_id,
                command.source_channel,
                command.correlation_id,
                {
                    "artifact_sha256": record.artifact_sha256,
                    "declared_media_type": command.declared_media_type,
                    "detected_media_type": record.detected_media_type,
                    "expected_byte_size": record.expected_byte_size,
                },
            )
            return record

    def review(self, command: ReviewEvidenceCommand) -> EvidenceRecord:
        self._authorize_write(
            command.matter_id,
            command.reviewer,
            command.source_channel,
            command.correlation_id,
            "REVIEW",
        )
        try:
            with self._repo.transaction() as connection:
                matter = self._repo.casework.lock_matter(connection, command.matter_id)
                self._require_l1_open(matter)
                record = self._repo.review(
                    connection,
                    matter_id=command.matter_id,
                    evidence_id=command.evidence_id,
                    expected_row_version=command.expected_row_version,
                    status=command.target_status,
                    reviewer=command.reviewer,
                    reviewed_at=command.reviewed_at,
                    reason=command.reason,
                )
                self._audit(
                    connection,
                    command.matter_id,
                    command.reviewer,
                    AuditEventType.EVIDENCE_REVIEW_RECORDED,
                    record.evidence_id,
                    command.source_channel,
                    command.correlation_id,
                    {
                        "review_status": record.review_status.value,
                        "row_version": record.row_version,
                    },
                )
                return record
        except EvidenceNotFound as exc:
            self._audit_denial(
                command.matter_id,
                command.reviewer,
                command.source_channel,
                command.correlation_id,
                command.evidence_id,
                "CROSS_MATTER_OR_NOT_FOUND",
                "REVIEW",
            )
            raise CrossMatterEvidenceDenied(
                "evidence is unavailable in the requested matter"
            ) from exc
        except TerminalReviewMutationDenied:
            self._audit_denial(
                command.matter_id,
                command.reviewer,
                command.source_channel,
                command.correlation_id,
                command.evidence_id,
                "TERMINAL_REVIEW_MUTATION",
                "REVIEW",
            )
            raise

    def link_checklist(self, command: LinkEvidenceChecklistCommand) -> EvidenceChecklistLink:
        self._authorize_write(
            command.matter_id,
            command.actor,
            command.source_channel,
            command.correlation_id,
            "CHECKLIST_LINK",
        )
        try:
            with self._repo.transaction() as connection:
                matter = self._repo.casework.lock_matter(connection, command.matter_id)
                self._require_l1_open(matter)
                self._repo.require(
                    connection,
                    matter_id=command.matter_id,
                    evidence_id=command.evidence_id,
                )
                pin = matter.assigned_playbook_version_id
                if pin is None or not self._repo.definition_has_item(
                    connection,
                    playbook_version_id=pin,
                    checklist_item_id=command.checklist_item_id,
                ):
                    raise InvalidChecklistAssociation(
                        "matter has no matching pinned checklist item"
                    )
                link = EvidenceChecklistLink(
                    matter_id=command.matter_id,
                    evidence_id=command.evidence_id,
                    playbook_version_id=pin,
                    checklist_item_id=command.checklist_item_id,
                    linked_by=command.actor,
                    linked_at=command.linked_at,
                )
                link, inserted = self._repo.link_checklist(connection, link)
                if inserted:
                    self._audit(
                        connection,
                        command.matter_id,
                        command.actor,
                        AuditEventType.EVIDENCE_CHECKLIST_LINKED,
                        command.evidence_id,
                        command.source_channel,
                        command.correlation_id,
                        {
                            "playbook_version_id": str(pin),
                            "checklist_item_id": command.checklist_item_id,
                        },
                    )
                return link
        except EvidenceNotFound as exc:
            self._audit_denial(
                command.matter_id,
                command.actor,
                command.source_channel,
                command.correlation_id,
                command.evidence_id,
                "CROSS_MATTER_OR_NOT_FOUND",
                "CHECKLIST_LINK",
            )
            raise CrossMatterEvidenceDenied(
                "evidence is unavailable in the requested matter"
            ) from exc
        except InvalidChecklistAssociation:
            self._audit_denial(
                command.matter_id,
                command.actor,
                command.source_channel,
                command.correlation_id,
                command.evidence_id,
                "INVALID_CHECKLIST_ASSOCIATION",
                "CHECKLIST_LINK",
            )
            raise
        except ChecklistLinkConflict:
            self._audit_independent(
                command.matter_id,
                command.actor,
                AuditEventType.EVIDENCE_PROVENANCE_CONFLICT,
                command.evidence_id,
                command.source_channel,
                command.correlation_id,
                "CHECKLIST_METADATA_CONFLICT",
                {
                    "checklist_item_id": command.checklist_item_id,
                    "reason_code": "CHECKLIST_METADATA_CONFLICT",
                },
            )
            raise

    def read(self, command: ReadEvidenceCommand) -> EvidenceRecord | list[EvidenceRecord]:
        with self._repo.transaction() as connection:
            self._repo.casework.require_matter(connection, command.matter_id)
            if command.evidence_id is None:
                return self._repo.list(connection, matter_id=command.matter_id)
            record = self._repo.get(
                connection, matter_id=command.matter_id, evidence_id=command.evidence_id
            )
        if record is None:
            self._audit_denial(
                command.matter_id,
                command.actor,
                command.source_channel,
                command.correlation_id,
                command.evidence_id,
                "CROSS_MATTER_OR_NOT_FOUND",
            )
            raise CrossMatterEvidenceDenied("evidence is unavailable in the requested matter")
        return record

    def ancestry(self, command: ReadEvidenceCommand) -> list[EvidenceDerivation]:
        if command.evidence_id is None:
            raise EvidenceNotFound("evidence_id is required for provenance traversal")
        with self._repo.transaction() as connection:
            self._repo.casework.require_matter(connection, command.matter_id)
            try:
                return self._repo.ancestry(
                    connection, matter_id=command.matter_id, evidence_id=command.evidence_id
                )
            except EvidenceNotFound:
                pass
        self._audit_denial(
            command.matter_id,
            command.actor,
            command.source_channel,
            command.correlation_id,
            command.evidence_id,
            "CROSS_MATTER_OR_NOT_FOUND",
        )
        raise CrossMatterEvidenceDenied("evidence is unavailable in the requested matter")

    def _authorize_write(
        self,
        matter_id: UUID,
        actor: str,
        source_channel: str,
        correlation_id: UUID | None,
        command_type: str,
    ) -> None:
        try:
            with self._repo.transaction() as connection:
                matter = self._repo.casework.require_matter(connection, matter_id)
                self._require_l1_open(matter)
        except (ClosedMatterEvidenceWriteDenied, EvidenceAuthorityDenied) as exc:
            self._audit_denial(
                matter_id,
                actor,
                source_channel,
                correlation_id,
                None,
                "CLOSED_MATTER"
                if isinstance(exc, ClosedMatterEvidenceWriteDenied)
                else "AUTHORITY_DENIED",
                command_type,
            )
            raise

    @staticmethod
    def _require_l1_open(matter: MatterRecord) -> None:
        if matter.status is MatterStatus.CLOSED:
            raise ClosedMatterEvidenceWriteDenied("closed matters reject evidence writes")
        if authority_rank(matter.action_authority_ceiling) < authority_rank(
            ActionAuthorityLevel.L1
        ):
            raise EvidenceAuthorityDenied(
                "matter authority ceiling does not permit L1 evidence writes"
            )

    @staticmethod
    def _metadata(command: UploadEvidenceCommand) -> dict[str, object]:
        return (
            {}
            if command.supplied_metadata is None
            else command.supplied_metadata.model_dump(mode="json", exclude_none=True)
        )

    def _audit_rejection(
        self, command: UploadEvidenceCommand, evidence_id: UUID, code: EvidenceRejectionCode
    ) -> None:
        self._audit_independent(
            command.matter_id,
            command.actor,
            AuditEventType.EVIDENCE_UPLOAD_REJECTED,
            evidence_id,
            command.source_channel,
            command.correlation_id,
            code.value,
            {
                "declared_media_type": command.declared_media_type,
                "expected_byte_size": command.expected_byte_size,
                "reason_code": code.value,
            },
        )

    @contextmanager
    def _provenance_conflict_boundary(
        self,
        command: RegisterDerivedEvidenceCommand,
        evidence_id: UUID,
        artifact_sha256: str,
    ) -> Iterator[None]:
        try:
            yield
        except (EvidenceProvenanceConflict, ProvenanceIntegrityConflict) as exc:
            self._audit_independent(
                command.matter_id,
                command.actor,
                AuditEventType.EVIDENCE_PROVENANCE_CONFLICT,
                evidence_id,
                command.source_channel,
                command.correlation_id,
                "PROVENANCE_CONFLICT",
                {
                    "artifact_sha256": artifact_sha256,
                    "source_evidence_id": str(command.source_evidence_id),
                    "reason_code": "PROVENANCE_CONFLICT",
                },
            )
            raise EvidenceProvenanceConflict(
                "derived evidence conflicts with authoritative provenance"
            ) from exc
        except (ClosedMatterEvidenceWriteDenied, EvidenceAuthorityDenied) as exc:
            self._audit_denial(
                command.matter_id,
                command.actor,
                command.source_channel,
                command.correlation_id,
                evidence_id,
                "CLOSED_MATTER"
                if isinstance(exc, ClosedMatterEvidenceWriteDenied)
                else "AUTHORITY_DENIED",
                "DERIVE",
            )
            raise

    def _audit_denial(
        self,
        matter_id: UUID,
        actor: str,
        source_channel: str,
        correlation_id: UUID | None,
        evidence_id: UUID | None,
        reason: str,
        command_type: str = "READ",
    ) -> None:
        self._audit_independent(
            matter_id,
            actor,
            AuditEventType.ACTION_DENIED,
            evidence_id,
            source_channel,
            correlation_id,
            reason,
            {
                "command_type": command_type,
                "required_level": "L1" if command_type != "READ" else "L0",
                "reason_code": reason,
            },
        )

    def _audit_independent(
        self,
        matter_id: UUID,
        actor: str,
        event_type: AuditEventType,
        evidence_id: UUID | None,
        source_channel: str,
        correlation_id: UUID | None,
        reason: str,
        metadata: dict[str, object],
    ) -> None:
        try:
            with self._repo.independent_transaction() as connection:
                self._audit(
                    connection,
                    matter_id,
                    actor,
                    event_type,
                    evidence_id,
                    source_channel,
                    correlation_id,
                    metadata,
                    reason,
                )
        except Exception as exc:
            raise EvidenceAuditWriteFailed(
                "required evidence denial audit could not be persisted"
            ) from exc

    def _audit(
        self,
        connection: Connection,
        matter_id: UUID,
        actor: str,
        event_type: AuditEventType,
        evidence_id: UUID | None,
        source_channel: str,
        correlation_id: UUID | None,
        metadata: dict[str, object],
        reason: str | None = None,
    ) -> None:
        try:
            self._repo.casework.append_audit_event(
                connection,
                event_id=uuid4(),
                matter_id=matter_id,
                actor=actor,
                event_type=event_type,
                entity_type="EVIDENCE",
                entity_id=evidence_id,
                correlation_id=correlation_id,
                reason=reason,
                source_channel=source_channel,
                metadata=metadata,
            )
        except Exception as exc:
            raise EvidenceAuditWriteFailed("required evidence audit could not be written") from exc

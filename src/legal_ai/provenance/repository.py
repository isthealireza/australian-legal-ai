"""Synchronous SQLAlchemy Core repository for immutable capture registration."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import Connection, Engine, RowMapping, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from legal_ai.db import source_document_captures

from .artifact_registry import ArtifactRegistry
from .content_store import ArtifactContent, LocalArtifactStore, StoredArtifact
from .errors import ProvenanceIntegrityConflict
from .models import FederalRegisterCapture


@dataclass(frozen=True, slots=True)
class SourceDocumentCaptureRecord:
    """Persisted immutable Federal Register capture metadata."""

    id: int
    source_system: str
    title_id: str
    register_id: str
    official_document_id: str
    official_source_url: str
    document_format: str
    volume: int | None
    retrieved_at: datetime
    response_content_type: str
    etag: str | None
    last_modified: str | None
    artifact_sha256: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CaptureRegistration:
    """Filesystem artifact and database capture returned as one result."""

    artifact: StoredArtifact
    capture: SourceDocumentCaptureRecord


class ProvenanceRepository:
    """Register filesystem artifacts and immutable provenance transactionally."""

    def __init__(
        self,
        bind: Engine | Connection,
        artifact_store: LocalArtifactStore,
    ) -> None:
        self._bind = bind
        self._artifact_store = artifact_store
        self._artifact_registry = ArtifactRegistry()

    def capture(
        self,
        content: ArtifactContent,
        *,
        provenance: FederalRegisterCapture,
        max_bytes: int,
    ) -> CaptureRegistration:
        """Publish bytes first, then register compatible metadata atomically."""

        artifact = self._artifact_store.store(
            content,
            max_bytes=max_bytes,
            expected_sha256=provenance.expected_sha256,
        )

        try:
            with self._transaction() as connection:
                self._artifact_registry.register(
                    connection, artifact, media_type=provenance.response_content_type
                )
                capture = self._insert_or_obtain_capture(connection, artifact, provenance)
        except IntegrityError as exc:
            raise ProvenanceIntegrityConflict(
                "database constraints rejected immutable provenance metadata"
            ) from exc

        return CaptureRegistration(artifact=artifact, capture=capture)

    @contextmanager
    def _transaction(self) -> Iterator[Connection]:
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

    @staticmethod
    def _insert_or_obtain_capture(
        connection: Connection,
        artifact: StoredArtifact,
        provenance: FederalRegisterCapture,
    ) -> SourceDocumentCaptureRecord:
        submitted = {
            "source_system": provenance.source_system,
            "title_id": provenance.title_id,
            "register_id": provenance.register_id,
            "official_document_id": provenance.official_document_id,
            "official_source_url": provenance.official_source_url,
            "document_format": provenance.document_format,
            "volume": provenance.volume,
            "retrieved_at": provenance.retrieved_at,
            "response_content_type": provenance.response_content_type,
            "etag": provenance.etag,
            "last_modified": provenance.last_modified,
            "artifact_sha256": artifact.sha256,
        }
        connection.execute(
            insert(source_document_captures)
            .values(**submitted)
            .on_conflict_do_nothing(constraint="uq_source_document_captures_source_document")
        )
        existing = (
            connection.execute(
                select(source_document_captures).where(
                    source_document_captures.c.source_system == provenance.source_system,
                    source_document_captures.c.official_document_id
                    == provenance.official_document_id,
                )
            )
            .mappings()
            .one()
        )
        compatibility_fields = {
            field: value for field, value in submitted.items() if field != "retrieved_at"
        }
        ProvenanceRepository._require_compatible(
            "source document capture",
            existing,
            compatibility_fields,
        )
        return ProvenanceRepository._capture_record(existing)

    @staticmethod
    def _require_compatible(
        identity: str,
        existing: RowMapping,
        submitted: Mapping[str, object],
    ) -> None:
        conflicting_fields = [
            field for field, value in submitted.items() if existing[field] != value
        ]
        if conflicting_fields:
            fields = ", ".join(sorted(conflicting_fields))
            raise ProvenanceIntegrityConflict(f"{identity} conflicts on {fields}")

    @staticmethod
    def _capture_record(row: RowMapping) -> SourceDocumentCaptureRecord:
        return SourceDocumentCaptureRecord(
            id=cast(int, row["id"]),
            source_system=cast(str, row["source_system"]),
            title_id=cast(str, row["title_id"]),
            register_id=cast(str, row["register_id"]),
            official_document_id=cast(str, row["official_document_id"]),
            official_source_url=cast(str, row["official_source_url"]),
            document_format=cast(str, row["document_format"]),
            volume=cast(int | None, row["volume"]),
            retrieved_at=cast(datetime, row["retrieved_at"]),
            response_content_type=cast(str, row["response_content_type"]),
            etag=cast(str | None, row["etag"]),
            last_modified=cast(str | None, row["last_modified"]),
            artifact_sha256=cast(str, row["artifact_sha256"]),
            created_at=cast(datetime, row["created_at"]),
        )

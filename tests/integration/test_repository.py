import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select

from legal_ai.db import artifacts, source_document_captures
from legal_ai.provenance import (
    FederalRegisterCapture,
    LocalArtifactStore,
    ProvenanceIntegrityConflict,
    ProvenanceRepository,
)

pytestmark = pytest.mark.integration


def _capture(**overrides: object) -> FederalRegisterCapture:
    data: dict[str, object] = {
        "title_id": "C2004A00109",
        "register_id": "C2026C00206",
        "official_document_id": "C2026C00206-primary-pdf-volume-1",
        "official_source_url": (
            "https://api.prod.legislation.gov.au/v1/documents/C2026C00206-primary-pdf-volume-1"
        ),
        "document_format": "Pdf",
        "volume": 1,
        "response_content_type": "application/pdf",
        "retrieved_at": datetime(2026, 7, 21, 3, 4, 5, tzinfo=UTC),
    }
    data.update(overrides)
    return FederalRegisterCapture.model_validate(data)


def _repository(
    engine: Engine,
    artifact_root: Path,
) -> ProvenanceRepository:
    return ProvenanceRepository(engine, LocalArtifactStore(artifact_root))


def test_first_artifact_and_capture_registration(
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    registration = _repository(migrated_engine, tmp_path).capture(
        [b"official ", b"bytes"],
        provenance=_capture(),
        max_bytes=14,
    )

    assert registration.artifact.sha256 == hashlib.sha256(b"official bytes").hexdigest()
    assert registration.artifact.byte_size == 14
    assert registration.capture.official_document_id == ("C2026C00206-primary-pdf-volume-1")
    assert registration.capture.artifact_sha256 == registration.artifact.sha256
    assert registration.capture.retrieved_at == datetime(
        2026,
        7,
        21,
        3,
        4,
        5,
        tzinfo=UTC,
    )


def test_same_capture_is_idempotent(
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    repository = _repository(migrated_engine, tmp_path)
    first = repository.capture(
        [b"same"],
        provenance=_capture(),
        max_bytes=4,
    )
    later_capture = _capture(
        retrieved_at=_capture().retrieved_at + timedelta(minutes=10),
    )
    second = repository.capture(
        [b"same"],
        provenance=later_capture,
        max_bytes=4,
    )

    assert second == first


def test_same_document_id_with_different_hash_fails_closed(
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    repository = _repository(migrated_engine, tmp_path)
    repository.capture([b"first"], provenance=_capture(), max_bytes=6)

    with pytest.raises(ProvenanceIntegrityConflict, match="artifact_sha256"):
        repository.capture([b"second"], provenance=_capture(), max_bytes=6)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title_id", "C2004A03712"),
        ("register_id", "C2026C00227"),
        (
            "official_source_url",
            "https://legislation.gov.au/document/C2026C00206-primary-pdf-volume-1",
        ),
        ("document_format", "Word"),
        ("volume", 2),
    ],
)
def test_same_document_id_with_conflicting_critical_provenance_fails_closed(
    migrated_engine: Engine,
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    repository = _repository(migrated_engine, tmp_path)
    repository.capture([b"same"], provenance=_capture(), max_bytes=4)

    with pytest.raises(ProvenanceIntegrityConflict, match=field):
        repository.capture(
            [b"same"],
            provenance=_capture(**{field: value}),
            max_bytes=4,
        )


def test_different_document_ids_can_reuse_one_artifact(
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    repository = _repository(migrated_engine, tmp_path)
    first = repository.capture([b"same"], provenance=_capture(), max_bytes=4)
    second = repository.capture(
        [b"same"],
        provenance=_capture(
            official_document_id="C2026C00206-primary-pdf-volume-2",
            official_source_url=(
                "https://api.prod.legislation.gov.au/v1/documents/C2026C00206-primary-pdf-volume-2"
            ),
            volume=2,
        ),
        max_bytes=4,
    )

    assert second.artifact == first.artifact
    assert second.capture.id != first.capture.id
    with migrated_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(artifacts)) == 1
        assert connection.scalar(select(func.count()).select_from(source_document_captures)) == 2


def test_failed_capture_registration_rolls_back_new_database_rows_but_keeps_blob(
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    repository = _repository(migrated_engine, tmp_path)
    repository.capture([b"first"], provenance=_capture(), max_bytes=6)
    orphan_hash = hashlib.sha256(b"second").hexdigest()

    with pytest.raises(ProvenanceIntegrityConflict):
        repository.capture([b"second"], provenance=_capture(), max_bytes=6)

    with migrated_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(artifacts)) == 1
        assert connection.scalar(select(func.count()).select_from(source_document_captures)) == 1
    assert list(tmp_path.rglob(f"{orphan_hash}.blob"))


def test_repository_accepts_existing_connection(
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    with migrated_engine.connect() as connection:
        registration = ProvenanceRepository(
            connection,
            LocalArtifactStore(tmp_path),
        ).capture([b"content"], provenance=_capture(), max_bytes=7)

    assert registration.capture.official_document_id == _capture().official_document_id


def test_repository_uses_savepoint_inside_caller_managed_transaction(
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    with migrated_engine.connect() as connection:
        outer_transaction = connection.begin()
        registration = ProvenanceRepository(
            connection,
            LocalArtifactStore(tmp_path),
        ).capture([b"content"], provenance=_capture(), max_bytes=7)

        assert registration.capture.official_document_id == _capture().official_document_id
        artifact_path = registration.artifact.path
        assert artifact_path.read_bytes() == b"content"
        assert connection.scalar(select(func.count()).select_from(artifacts)) == 1
        outer_transaction.rollback()

    assert artifact_path.read_bytes() == b"content"
    with migrated_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(artifacts)) == 0
        assert connection.scalar(select(func.count()).select_from(source_document_captures)) == 0


def test_concurrent_duplicate_registration_returns_one_record(
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    repository = _repository(migrated_engine, tmp_path)

    def register() -> int:
        return repository.capture(
            [b"concurrent"],
            provenance=_capture(),
            max_bytes=10,
        ).capture.id

    with ThreadPoolExecutor(max_workers=2) as executor:
        record_ids = list(executor.map(lambda _index: register(), range(2)))

    assert record_ids[0] == record_ids[1]


def test_repository_exposes_no_update_delete_or_arbitrary_execute_api(
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    repository = _repository(migrated_engine, tmp_path)

    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")
    assert not hasattr(repository, "execute")

"""Immutability and database-level guard integration tests for Phase 3 evidence."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Connection, Engine, func, insert, select, text, update
from sqlalchemy.exc import DBAPIError

from legal_ai.db import (
    casework_checklist_states,
    casework_evidence_checklist_links,
    casework_evidence_records,
    casework_matters,
    playbook_versions,
    playbooks,
)
from legal_ai.evidence.models import LinkEvidenceChecklistCommand
from legal_ai.provenance import ArtifactRegistry, LocalArtifactStore

from .test_evidence_repository import create_matter, service, upload_command


def _register_test_artifact(connection: Connection, tmp_path: Path) -> str:
    store = LocalArtifactStore(tmp_path)
    artifact = store.store([b"hello"], max_bytes=5)
    ArtifactRegistry().register(connection, artifact, media_type="text/plain")
    return artifact.sha256


def test_direct_update_and_delete_are_rejected(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    record = service(migrated_engine, tmp_path).upload(upload_command(matter_id), [b"hello"])
    with pytest.raises(DBAPIError), migrated_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE casework_evidence_records SET caller_filename='tampered.txt' "
                "WHERE evidence_id=:id"
            ),
            {"id": record.evidence_id},
        )
    with pytest.raises(DBAPIError), migrated_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM casework_evidence_records WHERE evidence_id=:id"),
            {"id": record.evidence_id},
        )


def test_derived_record_without_derivation_is_rejected_at_commit(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    vault.upload(upload_command(matter_id), [b"hello"])
    artifact = LocalArtifactStore(tmp_path).store([b"other"], max_bytes=5)
    with pytest.raises(DBAPIError), migrated_engine.begin() as connection:
        ArtifactRegistry().register(connection, artifact, media_type="text/plain")
        connection.execute(
            text(
                "INSERT INTO casework_evidence_records "
                "(evidence_id,matter_id,artifact_sha256,evidence_kind,evidence_role,"
                "caller_filename,declared_media_type,detected_media_type,"
                "expected_byte_size,registered_by) VALUES "
                "(gen_random_uuid(),:matter,:hash,'TEXT','DERIVED','x.txt',"
                "'text/plain','text/plain',5,'tester')"
            ),
            {"matter": matter_id, "hash": artifact.sha256},
        )


def test_checklist_link_uses_pin_is_immutable_and_does_not_change_state(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    evidence = service(migrated_engine, tmp_path).upload(upload_command(matter_id), [b"hello"])
    version_id = __import__("uuid").uuid4()
    with migrated_engine.begin() as connection:
        connection.execute(
            insert(playbooks).values(
                playbook_key="synthetic-checklist",
                display_name="Synthetic",
                created_by="tester",
            )
        )
        connection.execute(
            insert(playbook_versions).values(
                playbook_version_id=version_id,
                playbook_key="synthetic-checklist",
                version=1,
                status="ACTIVE",
                schema_version=1,
                definition_json={
                    "evidence_checklist": [{"checklist_item_id": "photos", "label": "Photos"}]
                },
                content_sha256="a" * 64,
                created_by="tester",
                updated_by="tester",
            )
        )
        connection.execute(
            update(casework_matters)
            .where(casework_matters.c.matter_id == matter_id)
            .values(assigned_playbook_version_id=version_id)
        )
    vault = service(migrated_engine, tmp_path)
    link = vault.link_checklist(
        LinkEvidenceChecklistCommand(
            matter_id=matter_id,
            evidence_id=evidence.evidence_id,
            checklist_item_id="photos",
            actor="tester",
            linked_at=datetime.now(UTC),
            source_channel="integration",
        )
    )
    assert link.playbook_version_id == version_id
    with migrated_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(casework_checklist_states)) == 0
    with pytest.raises(DBAPIError), migrated_engine.begin() as connection:
        connection.execute(update(casework_evidence_checklist_links).values(linked_by="tamper"))


# --- Evidence insert guard tests ---


def test_insert_guard_accepts_valid_uploded(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    with migrated_engine.begin() as connection:
        sha = _register_test_artifact(connection, tmp_path)
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO casework_evidence_records "
                "(evidence_id,matter_id,artifact_sha256,evidence_kind,evidence_role,"
                "caller_filename,declared_media_type,detected_media_type,"
                "expected_byte_size,registered_by) VALUES "
                "(gen_random_uuid(),:matter,:hash,'TEXT','ORIGINAL','x.txt',"
                "'text/plain','text/plain',5,'tester')"
            ),
            {"matter": matter_id, "hash": sha},
        )


def test_insert_guard_rejects_review_accepted(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    with migrated_engine.begin() as connection:
        sha = _register_test_artifact(connection, tmp_path)
    with pytest.raises(DBAPIError), migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO casework_evidence_records "
                "(evidence_id,matter_id,artifact_sha256,evidence_kind,evidence_role,"
                "caller_filename,declared_media_type,detected_media_type,"
                "expected_byte_size,registered_by,review_status) VALUES "
                "(gen_random_uuid(),:matter,:hash,'TEXT','ORIGINAL','x.txt',"
                "'text/plain','text/plain',5,'tester','REVIEW_ACCEPTED')"
            ),
            {"matter": matter_id, "hash": sha},
        )


def test_insert_guard_rejects_review_rejected(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    with migrated_engine.begin() as connection:
        sha = _register_test_artifact(connection, tmp_path)
    with pytest.raises(DBAPIError), migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO casework_evidence_records "
                "(evidence_id,matter_id,artifact_sha256,evidence_kind,evidence_role,"
                "caller_filename,declared_media_type,detected_media_type,"
                "expected_byte_size,registered_by,review_status) VALUES "
                "(gen_random_uuid(),:matter,:hash,'TEXT','ORIGINAL','x.txt',"
                "'text/plain','text/plain',5,'tester','REVIEW_REJECTED')"
            ),
            {"matter": matter_id, "hash": sha},
        )


def test_insert_guard_rejects_uploded_with_reviewed_by(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    with migrated_engine.begin() as connection:
        sha = _register_test_artifact(connection, tmp_path)
    with pytest.raises(DBAPIError), migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO casework_evidence_records "
                "(evidence_id,matter_id,artifact_sha256,evidence_kind,evidence_role,"
                "caller_filename,declared_media_type,detected_media_type,"
                "expected_byte_size,registered_by,reviewed_by) VALUES "
                "(gen_random_uuid(),:matter,:hash,'TEXT','ORIGINAL','x.txt',"
                "'text/plain','text/plain',5,'tester','reviewer')"
            ),
            {"matter": matter_id, "hash": sha},
        )


def test_insert_guard_leaves_no_row_on_failure(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    with migrated_engine.begin() as connection:
        sha = _register_test_artifact(connection, tmp_path)
    with pytest.raises(DBAPIError), migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO casework_evidence_records "
                "(evidence_id,matter_id,artifact_sha256,evidence_kind,evidence_role,"
                "caller_filename,declared_media_type,detected_media_type,"
                "expected_byte_size,registered_by,review_status) VALUES "
                "(gen_random_uuid(),:matter,:hash,'TEXT','ORIGINAL','x.txt',"
                "'text/plain','text/plain',5,'tester','REVIEW_ACCEPTED')"
            ),
            {"matter": matter_id, "hash": sha},
        )
    with migrated_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(casework_evidence_records)) == 0


def test_insert_guard_rejects_uploded_with_reviewed_at(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    with migrated_engine.begin() as connection:
        sha = _register_test_artifact(connection, tmp_path)
    with pytest.raises(DBAPIError), migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO casework_evidence_records "
                "(evidence_id,matter_id,artifact_sha256,evidence_kind,evidence_role,"
                "caller_filename,declared_media_type,detected_media_type,"
                "expected_byte_size,registered_by,reviewed_at) VALUES "
                "(gen_random_uuid(),:matter,:hash,'TEXT','ORIGINAL','x.txt',"
                "'text/plain','text/plain',5,'tester',now())"
            ),
            {"matter": matter_id, "hash": sha},
        )


def test_insert_guard_rejects_uploded_with_review_reason(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    with migrated_engine.begin() as connection:
        sha = _register_test_artifact(connection, tmp_path)
    with pytest.raises(DBAPIError), migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO casework_evidence_records "
                "(evidence_id,matter_id,artifact_sha256,evidence_kind,evidence_role,"
                "caller_filename,declared_media_type,detected_media_type,"
                "expected_byte_size,registered_by,review_reason) VALUES "
                "(gen_random_uuid(),:matter,:hash,'TEXT','ORIGINAL','x.txt',"
                "'text/plain','text/plain',5,'tester','not allowed')"
            ),
            {"matter": matter_id, "hash": sha},
        )

from pathlib import Path

import pytest
from sqlalchemy import Engine

from legal_ai.evidence.errors import CrossMatterEvidenceDenied
from legal_ai.evidence.models import ReadEvidenceCommand, RegisterDerivedEvidenceCommand

from .test_evidence_repository import create_matter, service, upload_command


def test_same_blob_has_separate_matter_identity_and_scoped_reads(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    first_matter, second_matter = create_matter(migrated_engine), create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    first = vault.upload(upload_command(first_matter), [b"hello"])
    second = vault.upload(upload_command(second_matter), [b"hello"])
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.evidence_id != second.evidence_id
    with pytest.raises(CrossMatterEvidenceDenied):
        vault.read(
            ReadEvidenceCommand(
                matter_id=second_matter,
                evidence_id=first.evidence_id,
                actor="tester",
                source_channel="integration",
            )
        )


def test_cross_matter_derivation_is_denied(migrated_engine: Engine, tmp_path: Path) -> None:
    first_matter, second_matter = create_matter(migrated_engine), create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    source = vault.upload(upload_command(first_matter), [b"hello"])
    command = RegisterDerivedEvidenceCommand(
        matter_id=second_matter,
        source_evidence_id=source.evidence_id,
        caller_filename="derived.txt",
        declared_media_type="text/plain",
        expected_byte_size=7,
        actor="tester",
        source_channel="integration",
        operation_code="NORMALIZE",
        operation_version="1",
        processor_version="runtime-1",
        deterministic=True,
    )
    with pytest.raises(CrossMatterEvidenceDenied):
        vault.register_derived(command, [b"derived"])

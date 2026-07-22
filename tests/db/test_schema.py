from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from legal_ai.db import artifacts, metadata, source_document_captures


def test_metadata_contains_only_the_bounded_provenance_tables() -> None:
    assert set(metadata.tables) == {
        "provenance_artifacts",
        "source_document_captures",
    }


def test_artifact_schema_declares_immutable_integrity_constraints() -> None:
    check_names = {
        constraint.name
        for constraint in artifacts.constraints
        if isinstance(constraint, CheckConstraint)
    }
    unique_names = {
        constraint.name
        for constraint in artifacts.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert artifacts.primary_key.columns.keys() == ["sha256"]
    assert check_names == {
        "ck_provenance_artifacts_sha256_lower_hex",
        "ck_provenance_artifacts_byte_size_positive",
        "ck_provenance_artifacts_storage_key_deterministic",
    }
    assert unique_names == {"uq_provenance_artifacts_storage_key"}


def test_capture_schema_has_restrictive_artifact_foreign_key() -> None:
    foreign_keys = [
        constraint
        for constraint in source_document_captures.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]

    assert len(foreign_keys) == 1
    assert foreign_keys[0].ondelete == "RESTRICT"
    assert source_document_captures.primary_key.columns.keys() == ["id"]

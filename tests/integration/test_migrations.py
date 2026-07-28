import uuid

import pytest
from alembic import command
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from .conftest import alembic_config

pytestmark = pytest.mark.integration

_REVISION = "0005_casework_core"
_PROVENANCE_TABLES = {
    "provenance_artifacts",
    "source_document_captures",
}


def test_alembic_upgrade_reaches_head(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            assert MigrationContext.configure(connection).get_current_revision() == _REVISION
    finally:
        engine.dispose()


def test_upgrade_creates_expected_tables_constraints_and_indexes(
    test_database_url: str,
) -> None:
    command.upgrade(alembic_config(test_database_url), "head")
    engine = create_engine(test_database_url)
    try:
        inspector = inspect(engine)
        assert _PROVENANCE_TABLES <= set(inspector.get_table_names())

        artifact_checks = {
            constraint["name"]
            for constraint in inspector.get_check_constraints("provenance_artifacts")
        }
        capture_checks = {
            constraint["name"]
            for constraint in inspector.get_check_constraints("source_document_captures")
        }
        capture_indexes = {
            index["name"] for index in inspector.get_indexes("source_document_captures")
        }
        artifact_uniques = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("provenance_artifacts")
        }
        capture_uniques = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("source_document_captures")
        }

        assert artifact_checks == {
            "ck_provenance_artifacts_byte_size_positive",
            "ck_provenance_artifacts_sha256_lower_hex",
            "ck_provenance_artifacts_storage_key_deterministic",
        }
        assert capture_checks == {
            "ck_source_document_captures_document_format",
            "ck_source_document_captures_source_system",
            "ck_source_document_captures_volume_nonnegative",
        }
        assert artifact_uniques == {"uq_provenance_artifacts_storage_key"}
        assert capture_uniques == {"uq_source_document_captures_source_document"}
        assert {
            "ix_source_document_captures_artifact_sha256",
            "ix_source_document_captures_title_register",
        } <= capture_indexes
    finally:
        engine.dispose()


def test_downgrade_removes_only_objects_owned_by_migration(
    test_database_url: str,
) -> None:
    config = alembic_config(test_database_url)
    command.upgrade(config, "head")
    sentinel = f"test_sentinel_{uuid.uuid4().hex}"
    engine = create_engine(test_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE TABLE "{sentinel}" (id integer PRIMARY KEY)'))

        command.downgrade(config, "base")

        tables_after_downgrade = set(inspect(engine).get_table_names())
        assert sentinel in tables_after_downgrade
        assert _PROVENANCE_TABLES.isdisjoint(tables_after_downgrade)
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS "{sentinel}"'))
        engine.dispose()
        command.upgrade(config, "head")

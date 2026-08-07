import uuid

import pytest
from alembic import command
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from .conftest import alembic_config

pytestmark = pytest.mark.integration

_REVISION = "0007_evidence_vault"
_PROVENANCE_TABLES = {
    "provenance_artifacts",
    "source_document_captures",
}
_EVIDENCE_TABLES = (
    "casework_evidence_checklist_links",
    "casework_evidence_derivations",
    "casework_evidence_records",
)
_PLAYBOOK_CLEANUP = (
    "casework_checklist_states_history",
    "casework_intake_answers_history",
    "casework_playbook_evaluation_candidates",
    "casework_playbook_evaluations",
    "playbook_audit_events",
    "playbook_versions",
)


def _clear_evidence_data(database_url: str) -> None:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        any_exist = False
        for table in _EVIDENCE_TABLES:
            if connection.execute(text(f"SELECT to_regclass('{table}') IS NOT NULL")).scalar_one():
                any_exist = True
        if not any_exist:
            return
        for table in _EVIDENCE_TABLES:
            connection.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER USER"))
        for table in _EVIDENCE_TABLES:
            connection.execute(text(f"DELETE FROM {table}"))
        for table in _EVIDENCE_TABLES:
            connection.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER USER"))
    engine.dispose()


def _clear_full_schema_data(database_url: str) -> None:
    _clear_evidence_data(database_url)
    engine = create_engine(database_url)
    with engine.begin() as connection:
        for table in _PLAYBOOK_CLEANUP:
            exists = connection.execute(
                text(f"SELECT to_regclass('{table}') IS NOT NULL")
            ).scalar_one()
            if not exists:
                continue
            connection.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER USER"))
        for sql in (
            "DELETE FROM casework_checklist_states",
            "DELETE FROM casework_checklist_states_history",
            "DELETE FROM casework_intake_answers",
            "DELETE FROM casework_intake_answers_history",
            "DELETE FROM casework_playbook_evaluation_candidates",
            "DELETE FROM casework_playbook_evaluations",
            "DELETE FROM playbook_audit_events",
            "UPDATE casework_matters SET assigned_playbook_version_id = NULL, "
            "playbook_assigned_at = NULL, playbook_assigned_by = NULL, "
            "case_type = CASE "
            "WHEN case_type = 'MOTOR_VEHICLE_PROPERTY_DAMAGE' THEN 'UNASSIGNED' "
            "ELSE case_type END",
            "DELETE FROM playbook_versions",
            "DELETE FROM playbooks",
        ):
            table = sql.removeprefix("DELETE FROM ").removesuffix(" SET").split(" ")[0]
            if sql.startswith("DELETE FROM "):
                table = sql[len("DELETE FROM ") :].split(" ")[0]
            elif sql.startswith("UPDATE "):
                table = sql[len("UPDATE ") :].split(" ")[0]
            exists = connection.execute(
                text(f"SELECT to_regclass('{table}') IS NOT NULL")
            ).scalar_one()
            if not exists:
                continue
            connection.execute(text(sql))
        for table in _PLAYBOOK_CLEANUP:
            exists = connection.execute(
                text(f"SELECT to_regclass('{table}') IS NOT NULL")
            ).scalar_one()
            if not exists:
                continue
            connection.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER USER"))
    engine.dispose()


def test_alembic_upgrade_reaches_head(test_database_url: str) -> None:
    _clear_full_schema_data(test_database_url)
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

        _clear_full_schema_data(test_database_url)
        command.downgrade(config, "base")

        tables_after_downgrade = set(inspect(engine).get_table_names())
        assert sentinel in tables_after_downgrade
        assert _PROVENANCE_TABLES.isdisjoint(tables_after_downgrade)
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS "{sentinel}"'))
        engine.dispose()
        command.upgrade(config, "head")

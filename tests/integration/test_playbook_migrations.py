"""Alembic upgrade/downgrade integration tests for 0006 playbook framework."""

from __future__ import annotations

import uuid
from uuid import uuid4

import pytest
from alembic import command
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text

from .conftest import alembic_config

pytestmark = pytest.mark.integration

_REVISION = "0006_playbook_framework"
_PRIOR = "0005_casework_core"
_PLAYBOOK_TABLES = {
    "playbooks",
    "playbook_versions",
    "playbook_audit_events",
    "casework_playbook_evaluations",
    "casework_playbook_evaluation_candidates",
    "casework_intake_answers",
    "casework_intake_answers_history",
    "casework_checklist_states",
    "casework_checklist_states_history",
}
_PROVENANCE_TABLES = {
    "provenance_artifacts",
    "source_document_captures",
}
_IMMUTABLE_CLEANUP = (
    "casework_checklist_states_history",
    "casework_intake_answers_history",
    "casework_playbook_evaluation_candidates",
    "casework_playbook_evaluations",
    "playbook_audit_events",
    "playbook_versions",
)


def _clear_playbook_data(engine: Engine) -> None:
    with engine.begin() as connection:
        for table_name in _IMMUTABLE_CLEANUP:
            connection.execute(text(f"ALTER TABLE {table_name} DISABLE TRIGGER USER"))
        connection.execute(text("DELETE FROM casework_checklist_states"))
        connection.execute(text("DELETE FROM casework_checklist_states_history"))
        connection.execute(text("DELETE FROM casework_intake_answers"))
        connection.execute(text("DELETE FROM casework_intake_answers_history"))
        connection.execute(text("DELETE FROM casework_playbook_evaluation_candidates"))
        connection.execute(text("DELETE FROM casework_playbook_evaluations"))
        connection.execute(text("DELETE FROM playbook_audit_events"))
        connection.execute(
            text(
                "UPDATE casework_matters SET assigned_playbook_version_id = NULL, "
                "playbook_assigned_at = NULL, playbook_assigned_by = NULL"
            )
        )
        connection.execute(text("DELETE FROM playbook_versions"))
        connection.execute(text("DELETE FROM playbooks"))
        for table_name in _IMMUTABLE_CLEANUP:
            connection.execute(text(f"ALTER TABLE {table_name} ENABLE TRIGGER USER"))


def test_upgrade_to_head_is_playbook_framework(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            assert MigrationContext.configure(connection).get_current_revision() == _REVISION
    finally:
        engine.dispose()


def test_playbook_tables_exist_after_upgrade(test_database_url: str) -> None:
    command.upgrade(alembic_config(test_database_url), "head")
    engine = create_engine(test_database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert _PLAYBOOK_TABLES <= tables
        assert _PROVENANCE_TABLES <= tables
    finally:
        engine.dispose()


def test_playbook_versions_transition_and_delete_triggers_exist(test_database_url: str) -> None:
    command.upgrade(alembic_config(test_database_url), "head")
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE tgrelid = 'playbook_versions'::regclass "
                    "AND NOT tgisinternal"
                )
            ).fetchall()
            names = {row[0] for row in rows}
            assert "trg_playbook_versions_transition_guard" in names
            assert "trg_playbook_versions_delete_guard" in names
    finally:
        engine.dispose()


def test_downgrade_refuses_when_playbook_row_exists(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    command.upgrade(config, "head")
    engine = create_engine(test_database_url)
    version_id = uuid4()
    digest = "a" * 64
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO playbooks (playbook_key, display_name, created_by) "
                    "VALUES ('migration_guard', 'Migration guard', 'migrator')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO playbook_versions ("
                    "playbook_version_id, playbook_key, version, status, schema_version, "
                    "definition_json, content_sha256, created_by, updated_by"
                    ") VALUES ("
                    ":vid, 'migration_guard', 1, 'DRAFT', 1, "
                    "CAST(:defn AS jsonb), :digest, 'migrator', 'migrator')"
                ),
                {
                    "vid": version_id,
                    "defn": '{"schema_version":1}',
                    "digest": digest,
                },
            )

        with pytest.raises(Exception, match="refusing to downgrade"):
            command.downgrade(config, _PRIOR)

        with engine.connect() as connection:
            assert MigrationContext.configure(connection).get_current_revision() == _REVISION
            count = connection.execute(
                text("SELECT count(*) FROM playbook_versions WHERE playbook_version_id = :vid"),
                {"vid": version_id},
            ).scalar_one()
            assert int(count) == 1
    finally:
        _clear_playbook_data(engine)
        engine.dispose()


def test_downgrade_empty_succeeds_and_provenance_survives_upgrade(
    test_database_url: str,
) -> None:
    config = alembic_config(test_database_url)
    command.upgrade(config, "head")
    engine = create_engine(test_database_url)
    sha = "b" * 64
    storage_key = f"sha256/{sha[:2]}/{sha[2:4]}/{sha}.blob"
    sentinel = f"test_playbook_sentinel_{uuid.uuid4().hex}"
    try:
        _clear_playbook_data(engine)
        with engine.begin() as connection:
            connection.execute(text(f'CREATE TABLE "{sentinel}" (id integer PRIMARY KEY)'))
            connection.execute(
                text(
                    "INSERT INTO provenance_artifacts "
                    "(sha256, byte_size, media_type, storage_key) "
                    "VALUES (:sha, 1, 'text/plain', :storage_key)"
                ),
                {"sha": sha, "storage_key": storage_key},
            )

        command.downgrade(config, _PRIOR)

        with engine.connect() as connection:
            assert MigrationContext.configure(connection).get_current_revision() == _PRIOR
            tables = set(inspect(connection).get_table_names())
            assert sentinel in tables
            assert _PLAYBOOK_TABLES.isdisjoint(tables)
            assert _PROVENANCE_TABLES <= tables
            count = connection.execute(
                text("SELECT count(*) FROM provenance_artifacts WHERE sha256 = :sha"),
                {"sha": sha},
            ).scalar_one()
            assert int(count) == 1

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert MigrationContext.configure(connection).get_current_revision() == _REVISION
            count = connection.execute(
                text("SELECT count(*) FROM provenance_artifacts WHERE sha256 = :sha"),
                {"sha": sha},
            ).scalar_one()
            assert int(count) == 1
            assert _PLAYBOOK_TABLES <= set(inspect(connection).get_table_names())
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS "{sentinel}"'))
            connection.execute(
                text("DELETE FROM provenance_artifacts WHERE sha256 = :sha"),
                {"sha": sha},
            )
        engine.dispose()
        command.upgrade(config, "head")


def test_casework_audit_triggers_still_present_after_0006(test_database_url: str) -> None:
    command.upgrade(alembic_config(test_database_url), "head")
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            assert MigrationContext.configure(connection).get_current_revision() == _REVISION
            rows = connection.execute(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE tgrelid = 'casework_audit_events'::regclass "
                    "AND NOT tgisinternal"
                )
            ).fetchall()
            names = {row[0] for row in rows}
            assert "trg_casework_audit_events_immutable_update" in names
            assert "trg_casework_audit_events_immutable_delete" in names
    finally:
        engine.dispose()

"""Casework-focused Alembic upgrade/downgrade integration tests."""

import uuid

import pytest
from alembic import command
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from .conftest import alembic_config

pytestmark = pytest.mark.integration

_REVISION = "0006_playbook_framework"
_CASEWORK_TABLES = {
    "casework_matters",
    "casework_parties",
    "casework_party_roles",
    "casework_fact_items",
    "casework_issues",
    "casework_deadlines",
    "casework_tasks",
    "casework_audit_events",
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


def test_casework_upgrade_reaches_head(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            assert MigrationContext.configure(connection).get_current_revision() == _REVISION
            tables = set(inspect(connection).get_table_names())
            assert _CASEWORK_TABLES <= tables
            assert _PROVENANCE_TABLES <= tables
            exists = connection.execute(
                text("SELECT to_regclass('casework_matter_reference_seq') IS NOT NULL")
            ).scalar_one()
            assert exists is True
    finally:
        engine.dispose()


def test_casework_downgrade_preserves_provenance_sentinel(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    command.upgrade(config, "head")
    sentinel = f"test_casework_sentinel_{uuid.uuid4().hex}"
    engine = create_engine(test_database_url)
    try:
        # Phase 2 downgrade refuses if playbook/pin/MOTOR case_type rows remain.
        with engine.begin() as connection:
            for table_name in (
                "casework_checklist_states_history",
                "casework_intake_answers_history",
                "casework_playbook_evaluation_candidates",
                "casework_playbook_evaluations",
                "playbook_audit_events",
                "playbook_versions",
            ):
                connection.execute(text(f"ALTER TABLE {table_name} DISABLE TRIGGER USER"))
            connection.execute(text("DELETE FROM casework_checklist_states"))
            connection.execute(text("DELETE FROM casework_checklist_states_history"))
            connection.execute(text("DELETE FROM casework_intake_answers"))
            connection.execute(text("DELETE FROM casework_intake_answers_history"))
            connection.execute(text("DELETE FROM casework_playbook_evaluation_candidates"))
            connection.execute(text("DELETE FROM casework_playbook_evaluations"))
            connection.execute(text("DELETE FROM playbook_audit_events"))
            connection.execute(text("DELETE FROM casework_audit_events"))
            connection.execute(text("DELETE FROM casework_tasks"))
            connection.execute(text("DELETE FROM casework_deadlines"))
            connection.execute(text("DELETE FROM casework_issues"))
            connection.execute(text("DELETE FROM casework_fact_items"))
            connection.execute(text("DELETE FROM casework_party_roles"))
            connection.execute(text("DELETE FROM casework_parties"))
            connection.execute(text("DELETE FROM casework_matters"))
            connection.execute(text("DELETE FROM playbook_versions"))
            connection.execute(text("DELETE FROM playbooks"))
            for table_name in (
                "casework_checklist_states_history",
                "casework_intake_answers_history",
                "casework_playbook_evaluation_candidates",
                "casework_playbook_evaluations",
                "playbook_audit_events",
                "playbook_versions",
                "casework_audit_events",
            ):
                connection.execute(text(f"ALTER TABLE {table_name} ENABLE TRIGGER USER"))
        with engine.begin() as connection:
            connection.execute(text(f'CREATE TABLE "{sentinel}" (id integer PRIMARY KEY)'))
            sha = "a" * 64
            storage_key = f"sha256/{sha[:2]}/{sha[2:4]}/{sha}.blob"
            connection.execute(
                text(
                    "INSERT INTO provenance_artifacts "
                    "(sha256, byte_size, media_type, storage_key) "
                    "VALUES (:sha, 1, 'text/plain', :storage_key)"
                ),
                {"sha": sha, "storage_key": storage_key},
            )

        command.downgrade(config, "0004_immutable_provenance")

        tables_after = set(inspect(engine).get_table_names())
        assert sentinel in tables_after
        assert _PROVENANCE_TABLES <= tables_after
        assert _CASEWORK_TABLES.isdisjoint(tables_after)
        with engine.connect() as connection:
            count = connection.execute(
                text("SELECT count(*) FROM provenance_artifacts")
            ).scalar_one()
            assert int(count) >= 1
            exists = connection.execute(
                text("SELECT to_regclass('casework_matter_reference_seq') IS NOT NULL")
            ).scalar_one()
            assert exists is False
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS "{sentinel}"'))
            connection.execute(text("DELETE FROM provenance_artifacts"))
        engine.dispose()
        command.upgrade(config, "head")


def test_casework_audit_triggers_exist_after_upgrade(test_database_url: str) -> None:
    command.upgrade(alembic_config(test_database_url), "head")
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
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

"""Evidence migration integration tests."""

from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

from .conftest import alembic_config

_PROJECT_ROOT = Path(__file__).parents[2]

_EVIDENCE_TABLES = (
    "casework_evidence_checklist_links",
    "casework_evidence_derivations",
    "casework_evidence_records",
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


def test_empty_downgrade_and_reupgrade(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    command.upgrade(config, "head")
    _clear_evidence_data(test_database_url)
    command.downgrade(config, "0006_playbook_framework")
    command.upgrade(config, "head")


def _cleanup_after_data_bearing_downgrade(database_url: str) -> None:
    cleanup = create_engine(database_url)
    try:
        with cleanup.begin() as connection:
            for table in _EVIDENCE_TABLES + ("casework_audit_events", "playbook_audit_events"):
                exists = connection.execute(
                    text(f"SELECT to_regclass('{table}') IS NOT NULL")
                ).scalar_one()
                if not exists:
                    continue
                connection.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER USER"))
            for table in _EVIDENCE_TABLES:
                exists = connection.execute(
                    text(f"SELECT to_regclass('{table}') IS NOT NULL")
                ).scalar_one()
                if not exists:
                    continue
                connection.execute(text(f"DELETE FROM {table}"))
            for table in ("casework_audit_events", "playbook_audit_events"):
                exists = connection.execute(
                    text(f"SELECT to_regclass('{table}') IS NOT NULL")
                ).scalar_one()
                if not exists:
                    continue
                connection.execute(text(f"DELETE FROM {table}"))
            for table in ("casework_matters",):
                exists = connection.execute(
                    text(f"SELECT to_regclass('{table}') IS NOT NULL")
                ).scalar_one()
                if not exists:
                    continue
                connection.execute(text(f"DELETE FROM {table}"))
            for table in _EVIDENCE_TABLES + ("casework_audit_events", "playbook_audit_events"):
                exists = connection.execute(
                    text(f"SELECT to_regclass('{table}') IS NOT NULL")
                ).scalar_one()
                if not exists:
                    continue
                connection.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER USER"))
    finally:
        cleanup.dispose()


def test_data_bearing_downgrade_refuses(
    migrated_engine: Engine, test_database_url: str, tmp_path: Path
) -> None:
    from .test_evidence_repository import create_matter, service, upload_command

    matter = create_matter(migrated_engine)
    service(migrated_engine, tmp_path).upload(upload_command(matter), [b"hello"])
    migrated_engine.dispose()
    with pytest.raises(DBAPIError):
        command.downgrade(alembic_config(test_database_url), "0006_playbook_framework")
    _cleanup_after_data_bearing_downgrade(test_database_url)


def test_clear_virgin_database_noops(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    command.downgrade(config, "base")
    _clear_evidence_data(test_database_url)
    command.upgrade(config, "head")


def test_clear_empty_evidence_tables_succeeds(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    command.upgrade(config, "head")
    _clear_evidence_data(test_database_url)
    with create_engine(test_database_url).connect() as connection:
        for table in _EVIDENCE_TABLES:
            count = connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            assert count == 0
        for table in _EVIDENCE_TABLES:
            enabled = connection.execute(
                text(
                    "SELECT NOT EXISTS (SELECT 1 FROM pg_trigger "
                    "WHERE tgrelid = to_regclass(:table)::regclass "
                    "AND tgenabled = 'D' AND tgisinternal = false)"
                ),
                {"table": table},
            ).scalar_one()
            assert enabled is True


def test_clear_then_downgrade_succeeds(test_database_url: str, tmp_path: Path) -> None:
    from .test_evidence_repository import create_matter, service, upload_command

    migrated = create_engine(test_database_url)
    command.upgrade(alembic_config(test_database_url), "head")
    matter = create_matter(migrated)

    service(migrated, tmp_path).upload(upload_command(matter), [b"hello"])
    migrated.dispose()
    assert not (_PROJECT_ROOT / "sha256").exists()
    _clear_evidence_data(test_database_url)
    command.downgrade(alembic_config(test_database_url), "0006_playbook_framework")
    command.upgrade(alembic_config(test_database_url), "head")


def test_cleanup_verifies_triggers_enabled(test_database_url: str) -> None:
    command.upgrade(alembic_config(test_database_url), "head")
    _clear_evidence_data(test_database_url)
    with create_engine(test_database_url).begin() as connection:
        for table in _EVIDENCE_TABLES:
            disabled = connection.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_trigger "
                    "WHERE tgrelid = to_regclass(:table)::regclass "
                    "AND tgenabled = 'D' AND tgisinternal = false)"
                ),
                {"table": table},
            ).scalar_one()
            assert disabled is False

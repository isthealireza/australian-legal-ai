import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, delete, text
from sqlalchemy.engine import make_url

from legal_ai.db import (
    artifacts,
    casework_audit_events,
    casework_checklist_states,
    casework_checklist_states_history,
    casework_deadlines,
    casework_fact_items,
    casework_intake_answers,
    casework_intake_answers_history,
    casework_issues,
    casework_matters,
    casework_parties,
    casework_party_roles,
    casework_playbook_evaluation_candidates,
    casework_playbook_evaluations,
    casework_tasks,
    playbook_audit_events,
    playbook_versions,
    playbooks,
    source_document_captures,
)

_PROJECT_ROOT = Path(__file__).parents[2]
_SAFE_TEST_HOSTS = frozenset({"localhost", "127.0.0.1", "postgres"})

_IMMUTABLE_CLEANUP_TABLES = (
    "casework_audit_events",
    "playbook_audit_events",
    "casework_playbook_evaluations",
    "casework_playbook_evaluation_candidates",
    "casework_intake_answers_history",
    "casework_checklist_states_history",
    "playbook_versions",
)


def alembic_config(database_url: str) -> Config:
    config = Config(str(_PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def test_database_url() -> str:
    database_url = os.environ.get("LEGAL_AI_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("LEGAL_AI_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    parsed = make_url(database_url)
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.drivername != "postgresql+psycopg"
        or parsed.database is None
        or "test" not in parsed.database.lower()
        or parsed.host not in _SAFE_TEST_HOSTS
    ):
        pytest.fail(
            "LEGAL_AI_TEST_DATABASE_URL must use postgresql+psycopg and a local test-named database"
        )
    return database_url


@pytest.fixture
def migrated_engine(test_database_url: str) -> Iterator[Engine]:
    command.upgrade(alembic_config(test_database_url), "head")
    engine = create_engine(test_database_url)
    with engine.begin() as connection:
        # Immutable / no-delete triggers block cleanup; disable only on disposable DBs.
        for table_name in _IMMUTABLE_CLEANUP_TABLES:
            connection.execute(text(f"ALTER TABLE {table_name} DISABLE TRIGGER USER"))
        connection.execute(delete(casework_checklist_states))
        connection.execute(delete(casework_checklist_states_history))
        connection.execute(delete(casework_intake_answers))
        connection.execute(delete(casework_intake_answers_history))
        connection.execute(delete(casework_playbook_evaluation_candidates))
        connection.execute(delete(casework_playbook_evaluations))
        connection.execute(delete(casework_audit_events))
        connection.execute(delete(playbook_audit_events))
        connection.execute(delete(casework_tasks))
        connection.execute(delete(casework_deadlines))
        connection.execute(delete(casework_issues))
        connection.execute(delete(casework_fact_items))
        connection.execute(delete(casework_party_roles))
        connection.execute(delete(casework_parties))
        connection.execute(delete(casework_matters))
        connection.execute(delete(playbook_versions))
        connection.execute(delete(playbooks))
        connection.execute(delete(source_document_captures))
        connection.execute(delete(artifacts))
        for table_name in _IMMUTABLE_CLEANUP_TABLES:
            connection.execute(text(f"ALTER TABLE {table_name} ENABLE TRIGGER USER"))
    try:
        yield engine
    finally:
        engine.dispose()

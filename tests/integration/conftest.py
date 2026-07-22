import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, delete
from sqlalchemy.engine import make_url

from legal_ai.db import artifacts, source_document_captures

_PROJECT_ROOT = Path(__file__).parents[2]
_SAFE_TEST_HOSTS = frozenset({"localhost", "127.0.0.1", "postgres"})


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
        connection.execute(delete(source_document_captures))
        connection.execute(delete(artifacts))
    try:
        yield engine
    finally:
        engine.dispose()

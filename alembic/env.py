"""Alembic runtime for the approved provenance metadata schema."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from legal_ai.db import metadata

_DATABASE_URL_ENV = "LEGAL_AI_DATABASE_URL"
_CONNECT_TIMEOUT_SECONDS = 10

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _database_url() -> str:
    configured_url = config.get_main_option("sqlalchemy.url")
    database_url = configured_url or os.environ.get(_DATABASE_URL_ENV)
    if database_url is None or not database_url.strip():
        raise RuntimeError(
            "Alembic database URL is required through programmatic sqlalchemy.url "
            f"or {_DATABASE_URL_ENV}"
        )

    parsed = make_url(database_url)
    if parsed.drivername != "postgresql+psycopg":
        raise RuntimeError("Alembic requires a synchronous postgresql+psycopg database URL")
    return database_url


def run_migrations_offline() -> None:
    """Run migrations using a configured URL without creating an Engine."""

    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations through a synchronous Psycopg-backed Engine."""

    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": _CONNECT_TIMEOUT_SECONDS},
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

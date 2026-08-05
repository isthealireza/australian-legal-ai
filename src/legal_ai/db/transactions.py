"""Explicit transaction ownership helpers for durable rejection records."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine


@contextmanager
def independent_transaction(bind: Engine | Connection) -> Iterator[Connection]:
    """Commit on a physical connection independent of any caller transaction."""

    engine = bind if isinstance(bind, Engine) else bind.engine
    with engine.begin() as connection:
        yield connection


__all__ = ["independent_transaction"]

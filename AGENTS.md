# AGENTS.md

## Cursor Cloud specific instructions

This is a **backend-only Python 3.13 library** (the Australian Legal Casework OS),
managed with `uv`. There is no API server, frontend, or LLM — the only runnable
entry point today is the playbook seed CLI, and the only runtime dependency is a
local PostgreSQL 16 database. Standard commands live in `README.md` and the
`Makefile`; the notes below only cover non-obvious cloud setup caveats.

### Toolchain / running commands
- `uv` is installed to `~/.local/bin` (already on `PATH` via `~/.bashrc`). The
  update script runs `uv sync --locked`, which also provisions Python 3.13. Always
  run project commands through `uv run --locked ...` so the pinned interpreter and
  locked deps are used.
- Lint/format/typecheck/test commands are in the `Makefile` and `README.md`
  (`ruff check`, `ruff format --check`, `mypy .`, `pytest`). `make check` runs all
  of them.

### PostgreSQL (required for integration tests + the seed CLI)
- Docker is installed but the daemon is **not** started automatically. Start it
  once per VM before using Postgres: `sudo dockerd > /tmp/dockerd.log 2>&1 &`
  (in this environment Docker requires `sudo`). Then `docker compose up -d` starts
  Postgres 16 on `127.0.0.1:5432` (user `legal_ai`, password
  `local-development-only`, db `legal_ai`).
- Integration tests (`tests/integration/`) are **skipped** unless
  `LEGAL_AI_TEST_DATABASE_URL` is set, and `tests/integration/conftest.py`
  enforces that the URL uses the `postgresql+psycopg` driver, a **local** host
  (`localhost`/`127.0.0.1`/`postgres`), and a database name **containing "test"**.
  The compose file only creates the `legal_ai` database, so create the test DB once:
  `docker compose exec -T postgres createdb -U legal_ai legal_ai_test`.
  Then run: `LEGAL_AI_TEST_DATABASE_URL=postgresql+psycopg://legal_ai:local-development-only@localhost:5432/legal_ai_test uv run --locked pytest -q tests/integration`
  (the fixture runs Alembic migrations automatically against the test DB).
- Pure unit tests need no DB: `uv run --locked pytest -q --ignore=tests/integration`.

### Seed CLI (the "hello world" application action)
- Requires `LEGAL_AI_DATABASE_URL` and a **migrated** database. Migrate first with
  `LEGAL_AI_DATABASE_URL=postgresql+psycopg://legal_ai:local-development-only@localhost:5432/legal_ai uv run --locked alembic upgrade head`,
  then run `uv run --locked python -m legal_ai.playbooks.cli seed-wa-motor-v1`.
  It seeds the `wa_motor_property_damage` playbook as **DRAFT** and is idempotent
  (`SEED_CREATED` on first run, `SEED_NOOP` afterwards).

### Governance note
- `ENGINEERING_WORKFLOW.md` / `PROJECT_GOVERNANCE.md` forbid committing to `main`,
  adding dependencies/services, or touching governance docs unless a task explicitly
  authorises it. Keep changes within the bounded task scope.

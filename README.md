# Australian Legal AI

## Project status

This repository is in Sprint 0. It contains the engineering foundation for a
portfolio-quality internal prototype for Alirad. It is not a law firm, does not
provide legal advice, and is not suitable for final legal decisions.

Sprint 0 contains no legal-answering, retrieval, ingestion, model, API, or
frontend functionality. The only Python package content is package metadata.
Sprint 0 coverage validates test and coverage wiring only; the package contains
no application statements, so meaningful coverage thresholds will be introduced
when application code exists.

## MVP boundary

The planned MVP is a grounded Australian small-business legislation research
assistant limited to an indexed corpus of official sources. Those capabilities
are deferred to later sprints and must follow the repository governance,
evidence, citation, and fail-closed requirements.

Never use real client data in this prototype. Development and testing must use
only synthetic or public data.

## Prerequisites

- Git
- [uv 0.11.29](https://docs.astral.sh/uv/) with Python 3.13 support
- Docker Desktop, or Docker Engine with Docker Compose
- Optional on Linux, macOS, or WSL: Make

The repository pins Python 3.13. `uv sync --locked` installs the required interpreter
when it is not already available.

## Tool versions

The initial foundation resolves the following versions. `uv.lock` is the source
of truth for Python development dependencies.

Sprint 0 was validated locally with uv 0.11.29. GitHub Actions is pinned
to uv 0.11.29; remote CI validation remains pending.

| Tool | Version |
|---|---|
| Python | 3.13 |
| uv (local and CI) | 0.11.29 |
| uv build backend | `>=0.11.29,<0.12` |
| Ruff | 0.15.22 |
| Mypy | 2.3.0 |
| Pytest | 9.1.1 |
| Pytest-cov | 7.1.0 |
| Pre-commit | 4.6.0 |
| Gitleaks | 8.30.1 |
| PostgreSQL | 16 (`pgvector/pgvector:pg16`) |

## Windows PowerShell setup

Make is not required on Windows. From the repository root:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/0.11.29/install.ps1 | iex"
uv --version
uv sync --locked
uv run --locked pytest
```

The PostgreSQL defaults are intentionally unsafe local-development values.
Docker Compose works without an `.env` file. To customize them locally:

```powershell
Copy-Item .env.example .env
```

Never place production credentials or real secrets in `.env`.

## Direct local quality commands

These commands work in PowerShell and are the underlying commands used by CI:

```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy .
uv run --locked pytest
uv run --locked pytest --cov
uv run --locked pre-commit run --all-files
```

CI also scans committed Git history with the single configured secret scanner:

```powershell
uv run --locked pre-commit run gitleaks-history --hook-stage manual --all-files
```

To apply Ruff formatting locally:

```powershell
uv run --locked ruff format .
```

## Optional Make commands

On Linux, macOS, or WSL:

```sh
make install
make lint
make format
make format-check
make typecheck
make test
make coverage
make check
```

## Local PostgreSQL

Start PostgreSQL 16 with pgvector and inspect its health:

```powershell
docker compose up -d
docker compose ps
```

The database port is exposed only on `127.0.0.1`. Stop the service with:

```powershell
docker compose down
```

The named volume persists local database data across normal shutdowns. No real
client data may be stored in it.

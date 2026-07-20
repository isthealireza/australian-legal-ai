# ADR 0002: Foundation tooling

- Status: Accepted
- Date: 2026-07-20

## Context

Sprint 0 needs a small, reproducible toolchain that works for local development
on Windows and validation on Linux CI without introducing application
frameworks or runtime dependencies.

## Decision

### Python 3.13

Python 3.13 is the project's pinned language version so local development, CI,
typing, and later application work share one supported language baseline.

### uv

uv manages the Python interpreter, dependency resolution, virtual environment,
and cross-platform lockfile through one tool. This keeps setup consistent across
Windows and Linux.

### Ruff

Ruff provides linting, import ordering, modernization checks, and deterministic
formatting with a single fast tool and centralized `pyproject.toml`
configuration.

### Mypy strict mode

Mypy runs in strict mode so typing gaps are surfaced at the foundation rather
than becoming established as the codebase grows.

### Pytest

Pytest is the test runner because it supports small unit tests now and can grow
to recorded-fixture and contract tests in later bounded sprints. Pytest-cov
provides the required local coverage command.

### PostgreSQL 16

PostgreSQL 16 is the approved local database baseline for later sprints. Sprint
0 starts only the database service and implements no persistence layer.

### pgvector

The PostgreSQL image includes pgvector so later retrieval evaluation can compare
lexical and vector approaches. Vector retrieval remains evaluation-gated and is
not implemented or assumed in Sprint 0.

### Docker Compose

Docker Compose supplies one repeatable, isolated local PostgreSQL service with a
named volume and healthcheck. It is local development configuration, not a
production deployment design.

### Linux CI with Windows local development

Development occurs primarily in Windows PowerShell, while CI runs on
`ubuntu-latest` using the same underlying uv quality commands. This combination
checks portability against the intended Linux server environment without making
Make a Windows prerequisite.

### Gitleaks

Gitleaks is the single secret scanner because it provides broad rules for
credentials across source and configuration formats, integrates with
pre-commit, and does not become an application runtime dependency. The normal
hook scans staged changes before commit, while CI runs the same pinned scanner
over committed Git history.

## Consequences

The foundation adds only development and build tooling; it adds no application
runtime dependencies. Any future framework, service, or integration requires a
separately bounded task.

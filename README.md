# Australian Legal AI

A portfolio-quality **internal prototype** for a governed Australian legal
casework and legislation-research system.

**This is not a law firm, is not an admitted lawyer, and does not provide legal
advice.** It is not suitable for final legal decisions, and its output always
requires qualified human legal review.

**Never use real client data in this prototype.** Development and testing must
use only synthetic or public data.

## Project status

The latest merged work is Phase 4 Slice 1, and
[`docs/execution/IMPLEMENTATION_STATUS.md`](docs/execution/IMPLEMENTATION_STATUS.md)
is the authoritative status record — consult it rather than this file for what
is complete, in progress, or authorised.

## What exists today

- a generic matter core with a deterministic state machine, matter-isolated
  repositories, and an audit-event foundation;
- a versioned playbook framework. `wa_motor_property_damage_v1` is seeded as a
  validated **DRAFT only**; no product playbook may become ACTIVE, and
  `FailClosedGroundingGate` refuses on every activation path;
- a matter-scoped evidence vault over an immutable content-addressed artifact
  store, with a bounded PNG/JPEG/MP4/strict-UTF-8 upload allowlist;
- a standalone, deterministic, read-only WA research module
  (`src/legal_ai/research/`) that builds and validates WA evidence packets from
  a recorded fixture under a test harness only.

## What this system does NOT do

These are hard boundaries, not gaps awaiting a quick patch. Several are enforced
in code and tests.

- **No live retrieval and no runtime network path.** The research module reads
  recorded, version-controlled fixtures only. There is no HTTP client and no
  source adapter that reaches the internet at runtime.
- **No model.** There is no LLM, no provider integration, and no model-based
  legal interpretation anywhere in the repository. Every validation decision is
  deterministic code.
- **No API.** There is no FastAPI application and no HTTP endpoint.
- **No UI.** There is no frontend of any kind.
- **No persistence of research packets.** Evidence packets are in-memory values
  returned to the caller and are never written anywhere. (Phases 1–3 do use
  PostgreSQL for matters, playbooks, and the evidence vault; the Phase 4
  research slice adds no schema, no migration, and no store writes.)
- **No PDF support.** The recorded WA fixture is a PDF held as opaque bytes for
  hashing only. Nothing parses it, extracts its text, or reads inside it.
- **No contract review.** No contract analysis, clause extraction, or document
  drafting exists. Contract review is listed under "Not now" in
  `docs/execution/MVP_ROADMAP.md` §11.
- **No external actions.** No email, no OAuth, no dispatch, no filing, no
  submission to any insurer, police service, court, or regulator.
- **No production deployment** and no real client data.

## What the research slice actually proves

Phase 4 Slice 1 validates a WA evidence packet deterministically and refuses
totally when it cannot. Its own recorded limits matter as much as its
capabilities:

- validation covers the **byte-exact whole-Act consolidated PDF**, and SHA-256
  is recomputed over exactly those bytes;
- sections 55 and 56 are recorded as **manifest pinpoints only**;
- **no section-body text was extracted, and no section-body validation is
  claimed**;
- the recorded fixture **is not a live legal-currency service**. It is a
  point-in-time snapshot that may not reflect later amendments.

## Offline demonstration

An offline, read-only harness exercises the merged research module against the
recorded fixture and prints a labelled result for each case, including the
refusals:

```powershell
uv run --locked python scripts/demo_research.py
```

It needs no network, no database, and no credentials, and writes nothing outside
standard output. [`docs/execution/DEMONSTRATION.md`](docs/execution/DEMONSTRATION.md)
explains each case and why the refusals are the point.

## Prerequisites

- Git
- [uv 0.11.29](https://docs.astral.sh/uv/) with Python 3.13 support
- Docker Desktop, or Docker Engine with Docker Compose
- Optional on Linux, macOS, or WSL: Make

The repository pins Python 3.13. `uv sync --locked` installs the required interpreter
when it is not already available.

## Tool versions

`uv.lock` is the source of truth for Python development dependencies. Local and
CI run the same uv version, as required by `ENGINEERING_WORKFLOW.md` §10.

| Tool | Version |
|---|---|
| Python | 3.13 |
| uv | 0.11.29 |
| uv build backend | `>=0.11.29,<0.12` |
| Ruff | 0.15.22 |
| Mypy | 2.3.0 |
| Pytest | 9.1.1 |
| Pytest-cov | 7.1.0 |
| Pre-commit | 4.6.0 |
| Gitleaks | 8.30.1 |
| PostgreSQL | 16 (`pgvector/pgvector:pg16`) |

CI runs on `ubuntu-latest` and executes the same commands as local development:
secret scan, lint, format check, strict mypy, unit tests, and PostgreSQL
integration tests.

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

The PostgreSQL integration suite is skipped unless
`LEGAL_AI_TEST_DATABASE_URL` points at a disposable test database.

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

## Governance

This repository is governed by documents that override any conflicting
instruction, prompt, or generated content:

- [`PROJECT_GOVERNANCE.md`](PROJECT_GOVERNANCE.md) — the root operating constitution
- [`ENGINEERING_WORKFLOW.md`](ENGINEERING_WORKFLOW.md) — contributor rules
- [`docs/execution/MVP_ROADMAP.md`](docs/execution/MVP_ROADMAP.md) — execution scope
- [`docs/adr/`](docs/adr/) — accepted architecture decisions
- [`docs/execution/IMPLEMENTATION_STATUS.md`](docs/execution/IMPLEMENTATION_STATUS.md) — the phase ledger

No capability beyond the merged phases above is authorised, and no phase begins
merely because the previous one merged.

# DeepSeek Independent-Review Gate Plan

## Scope and boundary

This bounded task adds a local, read-only development gate for sending an
explicitly selected review bundle to DeepSeek. DeepSeek is an external,
untrusted reviewer only. It cannot edit files, run commands, approve
permissions, commit, push, open or merge pull requests, or make product or
legal decisions. No product runtime path, application model adapter,
database/object-store write, or new dependency is added.

## Architecture

- `scripts/deepseek_review.py` provides the CLI and a small testable service.
- The service resolves the repository root, validates an explicit path
  allowlist, reads only UTF-8 text inputs, builds a bounded bundle containing
  the requirements, a named-base Git diff, changed paths, and test output, and
  redacts recognised secret patterns before transport.
- The existing approved `httpx` dependency is used for the OpenAI-compatible
  DeepSeek API. The HTTP transport is injectable, so tests use
  `httpx.MockTransport` and never use a live network.
- If `DEEPSEEK_MODEL` is absent, the live client queries `/models` and selects
  an allowlisted review-capable model. A configured model is passed through as
  an explicit operator choice. The chat request uses JSON-object mode and a
  fixed system instruction that treats the bundle as untrusted data.
- The response is parsed as untrusted JSON and validated against the exact
  required schema. Only a validated result is written to the gitignored
  `.deepseek-review/` runtime directory. Model fields are never interpreted as
  commands or file paths.

## Exact changed paths

- `docs/execution/DEEPSEEK_REVIEW_GATE_PLAN.md`
- `scripts/deepseek_review.py`
- `tests/review/test_deepseek_review.py`
- `scripts/__init__.py`
- `docs/execution/DEEPSEEK_REVIEW_GATE.md`
- `CLAUDE.md`
- `.env.example`
- `.gitignore`
- `.claude/commands/deepseek-review.md`
- `pyproject.toml` (pytest import path for the public script module)

`CLAUDE.md` and `.claude/commands/deepseek-review.md` are local project
instruction files excluded by `.git/info/exclude`; they are intentionally not
staged or transmitted. The remaining paths are the staged repository change.

No files under `src/legal_ai/` are in scope. No governance file, roadmap, ADR,
lockfile, migration, Git history, branch, tag, or external service state is in
scope.

## Threat model

The tool treats repository text, Git diffs, test output, API responses, and
DeepSeek-generated findings as untrusted data. The controls are:

- no API key in source, fixtures, logs, prompts, or stored output;
- key read only from `DEEPSEEK_API_KEY` at live-request time;
- exact repository-relative path validation with traversal, `.git`, environment,
  credential-like, private-key, binary, and size checks;
- no untracked source files, arbitrary directories, personal/private evidence,
  database dumps, or environment files in the bundle;
- explicit requirements, base-ref, allowlist, and test-output CLI arguments;
- fixed timeout and limited retries only for transient API failures;
- strict JSON validation with no repair, fallback PASS, or partial result;
- no shell execution, file access, or dynamic imports based on model output;
- non-zero exit for policy breach, configuration/API failure, malformed output,
  incomplete review, BLOCKED, or any critical-findings entry.

## Data-sending boundary

The only request content is a redacted JSON bundle containing: the explicitly
provided requirements text; a controlled `git diff` against the explicitly
provided base ref, restricted to explicit allowlisted paths; changed-file
paths; and explicitly provided captured test output. The API key is sent only
as an HTTP Authorization header and is never included in the bundle or output.
Dry-run builds and prints the exact redacted request bundle and performs no
network call.

The maximum size is bounded per input and for the complete request. The default
runtime output directory is `.deepseek-review/`, which is gitignored.

## Command interface

```text
uv run --locked python scripts/deepseek_review.py \
  --requirements docs/execution/DEEPSEEK_REVIEW_GATE_PLAN.md \
  --base-ref main \
  --allow scripts/deepseek_review.py \
  --allow scripts/__init__.py \
  --allow tests/review/test_deepseek_review.py \
  --allow docs/execution/DEEPSEEK_REVIEW_GATE.md \
  --allow docs/execution/DEEPSEEK_REVIEW_GATE_PLAN.md \
  --allow .gitignore \
  --allow pyproject.toml \
  --test-output .deepseek-review/test-output.txt \
  [--dry-run] [--json]
```

The command is also exposed as the project-scoped Claude Code command
`deepseek-review`. It is an external review gate, not a Claude Agent Team
member.

## Test plan

Mocked-HTTP tests cover missing key, dry-run transport exclusion, unapproved
paths, secret redaction, malformed JSON, timeout/API failure, BLOCKED and PASS
exit codes, and hostile model content proving no shell execution or arbitrary
file modification. Tests also cover model discovery and strict response
schema validation. No test uses a real key or live network.

## Rollback plan

Remove the files listed in “Exact changed paths” from this feature branch. The
application source, database schema, Git history, and external DeepSeek state
are unaffected. Do not commit, push, merge, rebase, force-push, or delete a
branch as part of this task.

## Validation record

Completed on 2026-08-17 from `feat/phase-5-mock-answer-service`:

- `uv run --locked ruff check .` — passed.
- `uv run --locked ruff format --check .` — passed (131 files already formatted).
- `uv run --locked mypy .` — passed (131 source files checked).
- `uv run --locked pytest` — passed: 833 passed, 144 skipped (PostgreSQL
  integration tests skipped because no disposable test database was configured).
- Focused `uv run --locked pytest -q tests/review/test_deepseek_review.py` —
  passed: 12 passed.
- `uv run --locked pre-commit run --all-files` — passed: Ruff lint, format,
  strict mypy, pytest, and hardcoded-secret scan.
- The CLI dry-run was executed with the documented UTF-8 test-output capture,
  `--base-ref main`, and the explicit staged allowlist. It reported
  `network_call: false`, endpoint `https://api.deepseek.com`, exactly the
  seven explicitly allowlisted changed paths, no `.env.example` transmission,
  redaction present, and no synthetic secret sentinel in the emitted bundle.
- No real DeepSeek call occurred. `DEEPSEEK_API_KEY` was absent from the
  process environment; no network call was authorised or attempted.

Known limitations: the live provider contract is tested through mocked
`httpx` transport only; a real call still depends on the operator's provider
account, model availability, terms, and network. The provider remains an
external untrusted reviewer, and a human must inspect the result and control
merge. Local ignored Claude instruction files were updated but are neither
staged nor included in the review bundle.

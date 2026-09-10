# DeepSeek independent-review gate

This is a local, read-only development gate. It sends one explicitly bounded,
redacted review bundle to DeepSeek after implementation and before reporting a
task complete. DeepSeek is an external reviewer only: it cannot edit this
repository, run commands, approve permissions, commit, push, open or merge a
pull request, or make a product/legal decision. A human owner still controls
review, merge, and release decisions.

The gate is development tooling, not product runtime wiring. It does not add a
legal-answering model, live source retrieval, persistence, external action, or
authority beyond L0 read-only review.

## Configuration

Set the key only in the process environment that runs a live review:

```powershell
$env:DEEPSEEK_API_KEY = "<supplied-at-runtime>"
$env:DEEPSEEK_MODEL = "deepseek-chat" # optional; otherwise /models is checked
```

The tool never reads a `.env` file. `DEEPSEEK_API_KEY` is never written to the
repository, bundle, test fixture, log, or runtime result. The base URL is fixed
to `https://api.deepseek.com`. If `DEEPSEEK_MODEL` is not set, the tool first
calls the provider's `/models` endpoint and selects `deepseek-chat`, then
`deepseek-reasoner`, only when one is advertised. If no supported model is
advertised, the gate fails closed and asks for an explicit model.

## Bundle policy

The bundle contains only:

- the explicitly supplied, tracked requirements file;
- a Git diff against the explicitly named base ref, restricted to every
  explicitly repeated `--allow` path;
- the changed-file paths from that controlled diff; and
- explicitly supplied UTF-8 captured test output.

The requirements and allowlist inputs must be tracked. The only untracked input
exception is captured test output under the gitignored `.deepseek-review/`
runtime directory. No other untracked source or file is accepted.

The gate rejects traversal, absolute paths, `.git`, environment files,
credential/private-key-like paths, database dumps, symlinks outside the
repository, binary/non-UTF-8 files, empty inputs, oversized files, oversized
diffs, oversized bundles, and changed paths outside the allowlist. Recognised
secret patterns are redacted before any request. It does not send environment
files, credentials, private evidence, personal data, database dumps, or files
outside the explicit inputs.

Per-input size is capped at 100,000 bytes, the diff at 300,000 bytes, and the
complete JSON bundle at 400,000 bytes. Requests use a fixed timeout and at most
two retries for timeout, rate-limit, and transient server failures.

## Dry-run inspection

Dry-run does not require an API key and makes no network call. It prints the
exact redacted JSON request envelope, including paths, changed paths, and
content, so it can be inspected before a live call:

```powershell
New-Item -ItemType Directory -Force .deepseek-review | Out-Null
uv run --locked pytest -q 2>&1 | Out-File -Encoding utf8 .deepseek-review/test-output.txt
uv run --locked python scripts/deepseek_review.py `
  --requirements docs/execution/DEEPSEEK_REVIEW_GATE_PLAN.md `
  --base-ref main `
  --allow scripts/deepseek_review.py `
  --allow scripts/__init__.py `
  --allow tests/review/test_deepseek_review.py `
  --allow docs/execution/DEEPSEEK_REVIEW_GATE.md `
  --allow docs/execution/DEEPSEEK_REVIEW_GATE_PLAN.md `
  --allow .gitignore `
  --allow pyproject.toml `
  --test-output .deepseek-review/test-output.txt `
  --dry-run --json
```

Review the output for scope and redaction before a live call. The example uses
the actual repository quality command and names each intended changed path;
adjust the base ref and allowlist to the task being reviewed. Environment files,
including `.env.example`, are intentionally excluded from the sent bundle.

## Live review and result

After the dry-run is safe, run the same command without `--dry-run` and with
`DEEPSEEK_API_KEY` present. Use `--json` for the exact validated result shape,
or omit it for a concise human-readable verdict:

```powershell
uv run --locked python scripts/deepseek_review.py `
  --requirements docs/execution/DEEPSEEK_REVIEW_GATE_PLAN.md `
  --base-ref main `
  --allow scripts/deepseek_review.py `
  --allow scripts/__init__.py `
  --allow tests/review/test_deepseek_review.py `
  --allow docs/execution/DEEPSEEK_REVIEW_GATE.md `
  --allow docs/execution/DEEPSEEK_REVIEW_GATE_PLAN.md `
  --allow .gitignore `
  --allow pyproject.toml `
  --test-output .deepseek-review/test-output.txt `
  --json
```

Validated results are saved only under `.deepseek-review/`, which is ignored by
Git. Model output is treated as data: it is schema-validated, secret-redacted,
and never used as a shell command, path, import, or instruction.

The exact required model result is:

```json
{
  "verdict": "PASS",
  "summary": "string",
  "critical_findings": [],
  "required_fixes": [],
  "test_gaps": [],
  "scope_risks": []
}
```

The parser requires exactly the specified keys and finding fields. Malformed
JSON, schema violations, missing configuration, policy failures, API failures,
timeouts, incomplete reviews, and `BLOCKED` all return non-zero. Exit code 0 is
reserved for `PASS` with no entries in `critical_findings`.

## Claude Code command

The project-scoped `deepseek-review` command points to this safe CLI. It is a
review gate, not a native Claude Agent Team member. It must be run after code
changes and before reporting the task complete; a failed or skipped review is
not a PASS. The local `CLAUDE.md` and `.claude/` command are excluded by this
repository's local Git ignore and are not transmitted as review inputs.

## Tests and rollback

`tests/review/test_deepseek_review.py` uses mocked HTTP only. It covers missing
key, dry-run network exclusion, path policy, redaction, malformed output,
timeouts/API failures, BLOCKED/PASS exit codes, and hostile model output.

Rollback is limited to removing the task's changed files from the feature
branch. No product source, schema, migration, Git history, branch, tag, or
external DeepSeek state is changed by rollback.

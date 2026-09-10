# Ruflo Codex Remediation Scope Card — Address chatgpt-codex-connector findings on PR #34

**Branch:** `fix/codex-review-ruflo-init`
**Governing decisions:** ENGINEERING_WORKFLOW.md rules 7, 10; Codex bot review on PR #34 (2026-09-10T07:16Z)
**Authority level:** L0 — infrastructure/config only; no product logic
**Status:** implemented, gates passing

## Goal

Address the four P1/P2 findings raised by the Codex bot after merging PR #34 (Ruflo V3 init):

1. **P1** `.mcp.json` — Windows-only `cmd` launcher breaks Linux/macOS environments; use cross-platform `npx`.
2. **P1** `.mcp.json` — `ruflo@latest` is an unpinned floating tag; pin to the reviewed version `3.40.0`.
3. **P2** `.claude-flow/memory-package.json` — contains an absolute Windows path (`C:\Users\Alpha\...`), violating ENGINEERING_WORKFLOW.md rule 7; remove from git tracking and gitignore.
4. **P2** `.claude-flow/metrics/v3-progress.json` — mutable runtime state committed to the repo; remove from git tracking and gitignore.

## Delivered

| Path | Change |
|---|---|
| `.mcp.json` | `command` changed from `cmd` to `npx`; `/c` arg removed; version pinned to `ruflo@3.40.0` |
| `.claude-flow/.gitignore` | Added `memory-package.json` and `metrics/` rules |
| `.claude-flow/memory-package.json` | Removed from git (`git rm --cached`) |
| `.claude-flow/metrics/v3-progress.json` | Removed from git (`git rm --cached`) |

## Out of scope — deliberately not done

- Any change to Python source, tests, or migrations
- Any change to ADRs, governance docs, or existing scope cards
- Any change to product logic, API, or legal-answering pipeline
- Any change to CI configuration

## Acceptance criteria

- `ruff check .` passes — PASS
- `ruff format --check .` passes — PASS
- `mypy .` passes — PASS
- `pytest` passes — 1351 passed, 148 skipped
- `.mcp.json` `command` is `npx` (cross-platform); `ruflo` version is pinned to `3.40.0`
- `.claude-flow/memory-package.json` and `.claude-flow/metrics/` are gitignored and untracked

## Risk acceptance

**Git history retains the absolute Windows path** in `.claude-flow/memory-package.json` at commit `d42af7b` (merged via PR #34). The path (a machine-local npm-cache resolver path of the form `C:\Users\<user>\AppData\Local\npm-cache\...`) is not a credential, secret, API key, or personally-identifying value. It does not enable repository access, authentication, or any privileged operation. History purge (filter-repo / BFG) is not warranted for a local filesystem path that is inherently machine-specific and carries no security value to an attacker. Risk accepted by repository owner.

## Rollback

`git revert HEAD` on the fix branch, or drop the branch before merge.

# Integration Merge Scope Card — Phase 5 stack onto main

**Branch:** `integrate/phase-5-onto-main`
**Merge base (first parent):** stack tip `f5c289a` (Phase 5 corpus expansion: WA
corpus, ingest script, py.typed-marker as a sibling).
**Second parent (merged in):** `main` `6f47c3f`.
**Owner decisions 2026-09-08 on the merge block:**
1. ADR numbering — main is canonical (0014/0015/0016 stay). Our Phase 5 ADRs
   renumbered: grounded-answering `0014 → 0019`, derived-provision `0015 → 0020`.
   `0017`/`0018` reserved for the unmerged E0-A/E0-B lineage.
2. Section-text mechanism — keep BOTH (`*.sections.json` companion + digest-chained
   `provisions/*.provision.json`). digests-chained store is canonical for new acts.
   Converge = follow-up needing its own ADR.

## Goal

Bring the Phase 5 stack onto current main with a MERGE (not rebase). No force
push, no amend, no drop. Resolve the ADR-README conflict; renumber our ADRs.

## Merged

- Merge commit `44a47b1` (merge `main` into the stack).
- Renumber commit `ae611bc` (rename ADRs 0019/0020 + reference updates, content
  unchanged).

## Conflicts

- `docs/adr/README.md` — resolved per owner decision 1 (list main 0014-0016, then
  our 0019-0020, add the 0017/0018 reservation line). This was the only true
  two-sided conflict.
- The other four files in the task brief were one-sided-only: `corpus.py`,
  `models.py`, `IMPLEMENTATION_STATUS.md` (changed only by main), and the
  `*.sections.json` fixture (main-only addition) auto-merged cleanly.

## Out of scope

No feature work, no new fixtures, no refactor. `src/legal_ai/research/corpus.py`,
`models.py` and the section-records path are main's (Phase 4 Slice 2), taken as-is.

## ADR renumber verification (rename + deletion)

Per owner decision 1, the two Phase 5 ADR files were renamed (git mv, content
unchanged) and the old filenames were removed:

| Old (renamed away) | New (renamed to) |
|---|---|
| `docs/adr/0014-phase-5-grounded-answering-and-read-only-api.md` | `docs/adr/0019-phase-5-grounded-answering-and-read-only-api.md` |
| `docs/adr/0015-derived-provision-text-live-provider-and-entailment.md` | `docs/adr/0020-derived-provision-text-live-provider-and-entailment.md` |

Verified on the merge branch HEAD (`git ls-files docs/adr/`):

- The two old filenames are **absent** — no file named `0014-phase-5-grounded-*`
  or `0015-derived-*` remains tracked.
- The two new filenames `0019-phase-5-*` and `0020-derived-*` are present.
- main's `0014-phase-4-slice-2-*` and `0015-phase-5-slice-1-*` remain, untouched.

There is therefore exactly one file per ADR number; no duplicate ADR file name
exists in the merged tree. The old files were not left as unreferenced copies:
they were removed by the rename. (This is a documentation/verification note; the
rename is also expressed by git's rename detection in the diff.)

## Validation notes

- ruff / ruff format --check / mypy: green.
- `pytest -m "not integration"`: 1196 passed, 47 skipped, 100 deselected, and 2
  failed — both `test_sections.py` symlink tests (`WinError 1314`). These are
  **main's own tests**, byte-identical to `main`, added by main's `bb9411e`, and
  documented in `main:docs/execution/ORCHESTRATION_FOUNDATION_SCOPE_CARD.md:68`
  as failing on a non-elevated Windows shell and passing on Ubuntu CI. Not a
  merge regression; not weakened or skipped.

## Rollback

The merge branch can be dropped; `main` is untouched. Reverting the renumber
commit restores ADR 0014/0015 filenames and references.

## Confirmed pre-existing defect on main — ORCH-001 (not fixed in this task)

The external review gate identified an off-by-one in main's orchestration
retry guard. It is main's code, merged in as-is, and this task left it
untouched per the owner's instruction (no feature work, no refactor). It is
recorded here so it is not lost.

- **File:** `src/legal_ai/orchestration/state_machine.py`
- **Defect:** the retry guard rejects a `FAILED → READY` transition when
  `attempt >= max_attempts`. With `max_attempts = N`, only attempts `1 .. N-1`
  may retry, so the final configured attempt never runs. The guard must allow
  the `N`th attempt.
- **Needs:** its own bounded task and a regression test that fails before the
  fix (asserting the exact `max_attempts` configured attempts are permitted).
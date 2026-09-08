# Scenario Test Suite — Task Scope Card

**Status:** tests only. Implementation is a scenario test suite under `tests/scenarios/`.
**Branch:** `test/scenario-suite` (from `fix/orchestration-retry-off-by-one` @ `46b768e`).
**Date:** 2026-09-08.

## Bounded goal

Add an offline, deterministic scenario test suite that exercises the grounded WA
legislation research pipeline (`src/legal_ai/research/` and the Phase 5
grounded answering boundary) from the outside. **No production code is
touched** — `src/legal_ai/` is out of scope, as are governance files.

## The grounding hard rule

The suite writes SCENARIOS, never LAW. Every expected Act title, section
number, provision heading, version, date, URL, digest and legal status is
copied verbatim from a manifest under `tests/fixtures/wa_legislation/` or from
the provision metadata derived from those manifests. If a scenario needs a
provision the corpus does not hold, the expected outcome is a typed refusal,
never an invented citation. A fabricated citation inside a passing test is a
release-blocking defect.

## Families

1. **Grounded** — the corpus holds the provision: validated packet, correct
   pinpoint, citation resolving to a recorded digest.
2. **Out of corpus** — a real Australian Act not recorded: refusal.
3. **Wrong jurisdiction** — NSW/Victorian problems against a WA corpus:
   `JURISDICTION_MISMATCH`.
4. **Ambiguous facts** — under-specified dates, parties or legal category: the
   pipeline refuses (its ask-state) rather than answers.
5. **Prompt injection** — instructions hidden in the user text and inside a
   retrieved excerpt: instruction inert, packet still validates.
6. **Tampered evidence** — mutated digest, foreign host, stale version:
   fail-closed refusal with the correct code.
7. **Scope refusal** — contract-review and document-upload requests, out of
   scope by name (MVP roadmap §11 "Not now"): refusal.
8. **Near miss** — section numbers that exist in one recorded Act but are asked
   about another recorded Act; repealed/renumbered or adjacent-but-unrecorded
   provisions (e.g. Motor Vehicle Dealers s 3, s 4, s 6, s 7; Owner-Drivers
   s 5): refusal, never a plausible neighbouring answer.

## Rules

- Offline only; no live network in any test.
- Deterministic assertions; no dependency on model wording.
- Every test names the exact fixture and section it relies on.
- Any expected value that cannot be grounded is written as a typed refusal with
  a comment saying why.

## Files in scope

- `tests/scenarios/__init__.py`
- `tests/scenarios/conftest.py`
- `tests/scenarios/test_grounded.py`
- `tests/scenarios/test_out_of_corpus.py`
- `tests/scenarios/test_wrong_jurisdiction.py`
- `tests/scenarios/test_ambiguous_facts.py`
- `tests/scenarios/test_prompt_injection.py`
- `tests/scenarios/test_tampered_evidence.py`
- `tests/scenarios/test_scope_refusal.py`
- `tests/scenarios/test_near_miss.py`
- `docs/execution/SCENARIO_SUITE_SCOPE_CARD.md` (this card)

## Acceptance criteria

- `uv run ruff check tests/scenarios`
- `uv run ruff format --check tests/scenarios`
- `uv run mypy tests/scenarios`
- `uv run pytest -m "not integration"` — green
- DeepSeek independent review gate: `PASS` with no `critical_findings`
  (recorded under `.deepseek-review/`).

## Out of scope / forbidden

- Any edit to `src/legal_ai/`, `PROJECT_GOVERNANCE.md`,
  `ENGINEERING_WORKFLOW.md`, `MVP_ROADMAP.md`, `LEGAL_AI_MASTER_BLUEPRINT.md`,
  existing ADRs, or Git tags.
- Fixing any pipeline defect the suite exposes (defects are reported, not
  fixed, in this task).
- Live network calls, model-worded assertions, or expected values drawn from
  anything other than the recorded fixtures.

## Rollback

Delete branch `test/scenario-suite` (no merge). `fix/orchestration-retry-off-by-one`
and all other branches are untouched; `src/legal_ai/` and governance files are
byte-identical to the baseline.
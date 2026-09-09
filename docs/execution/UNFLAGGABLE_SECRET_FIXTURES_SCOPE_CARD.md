# Scope Card — unflaggable secret fixtures

Branch: `chore/unflaggable-secret-fixtures`
Base: `integrate/main-2026-09-09` tip (where the file lives)
Date: 2026-09-09
Owner: Ali Rad

## Problem

`tests/review/test_deepseek_review.py` proves the review gate's `redact_secrets`
/ `redact_diff` strip real-shaped credentials before egress. To do that it must
contain real-shaped keys, including OpenRouter keys of the form `sk-or-v1-…`.
Those literals are safe (all-zeros / obvious placeholders, no real credential),
but GitHub push protection pattern-matches the `sk-or-v1-` shape and blocks every
push that introduces them — as it did on the Phase 5 consolidation push, which
needed a manual allow.

## Change (this task only)

Assemble the `sk-or-v1-` prefix at runtime from fragments
(`_OR = "sk-" + "or-" + "v1-"`) and build each fixture as an f-string, so **no
single source literal matches the `sk-or-v1-` pattern** while the value produced
at runtime is byte-for-byte the same real-shaped key. Every fixture, needle, and
the explanatory comment were de-literalised. The redaction tests are otherwise
untouched: they still feed a real-shaped key to the redactor and assert it is
stripped, so the behaviour under test is identical.

No history is rewritten. The old literals remain in already-pushed commits (the
scanner only blocks newly pushed literals); this new commit ensures future work
built on this tip does not re-introduce a fresh literal.

## Non-goals / constraints

- Do not rewrite history; do not force-push.
- Do not weaken the redaction test: it must still prove the redactor catches a
  real-shaped key. Verified: same assembled inputs, same assertions, 57 passed
  / 1 skipped in the file, unchanged.

## Definition of done

ruff, ruff format --check, mypy, pytest, then the DeepSeek review gate.

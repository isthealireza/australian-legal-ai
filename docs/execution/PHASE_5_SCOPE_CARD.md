# Phase 5 Scope Card — Grounded Answering, Read-Only API, and a Live Provider

**Branch:** `feat/phase-5-grounded-answer-api`
**Governing decisions:** [ADR 0014](../adr/0014-phase-5-grounded-answering-and-read-only-api.md) · [ADR 0015](../adr/0015-derived-provision-text-live-provider-and-entailment.md) (both Proposed)
**Authority level:** L0 — deterministic, read-only
**Status:** implemented and validated; review gate still BLOCKED — **not merge-ready**

## Goal

Turn the merged Phase 4 research module into a usable system: a question
becomes either a fully cited answer grounded in real statutory text, or an
explicit refusal.

## Delivered

| Path | Purpose |
|---|---|
| `src/legal_ai/answering/` | Answer-model protocol, mock adapter, citation validation (levels 1–2), audit sinks, pipeline |
| `src/legal_ai/answering/provisions.py` | Digest-chained derived provision text; refuses any broken chain |
| `src/legal_ai/answering/providers/openrouter.py` | Live adapter; model cannot influence its own citation |
| `src/legal_ai/answering/verification.py` | Level-3 entailment as an independent second call |
| `src/legal_ai/api/` | FastAPI factory, settings, schemas, health and research routes |
| `static/` | Single-page interface with the required permanent notices |
| `scripts/derive_wa_provisions.py` | Operator tool deriving provision text from the verified PDF |
| `tests/answering/`, `tests/api/` | 76 unit and HTTP contract tests |
| `docs/adr/0014-*.md`, `docs/adr/0015-*.md` | Decision records |
| `scripts/deepseek_review.py` | Review-gate repair: current model candidates, realistic read timeout |

## Out of scope — deliberately not done

Live retrieval at request time · database · authentication · corpus expansion
beyond provisions of the already-recorded Act · Commonwealth sources · vector
retrieval · matter, casework, evidence-vault or playbook surfaces · deployment ·
real client data · any L1+ authority · any change to a Phase 0–4 module.

## Acceptance criteria

1. Answerable question returns propositions carrying Act, pinpoint, version,
   source URL, and SHA-256. — **met**
2. Out-of-corpus, wrong-jurisdiction, and unknown-pinpoint questions each return
   an explicit typed refusal. — **met**
3. A citation the packet does not support refuses the whole answer. — **met**
4. A quote absent from the verified text refuses. — **met**
5. A broken provenance chain resolves no text rather than trusting it. — **met**
6. A live provider cannot assert a citation of its own. — **met**
7. Entailment `NOT_SUPPORTED`, an unreachable verifier, and an unparseable
   verdict all refuse. — **met**
8. A stray credential does not switch on a live provider. — **met**
9. Both notices appear permanently in the interface and on every response. — **met**
10. All repository gates pass. — **met**

## Validation

```
uv run ruff check .          # passes, excluding untracked scripts/wf5_structural_lint.py
uv run ruff format --check . # passes, same exclusion
uv run mypy .                # passes, same exclusion
uv run pytest -m "not integration"   # 957 passed, 46 skipped
```

The exclusion is a pre-existing untracked local file outside this task's scope.
It is the sole source of every remaining lint and type error.

Tests never call a network. The live adapter and verifier are exercised through
`httpx.MockTransport`.

## Running it

Mock model, no credentials, no network:

```
LEGAL_AI_WA_CORPUS_ROOT=tests/fixtures/wa_legislation \
LEGAL_AI_RESEARCH_AUDIT_LOG=.local/audit/research.jsonl \
uv run uvicorn legal_ai.api.main:create_app --factory --port 8099
```

Live model. Entailment verification is **required** with a live provider
(ADR 0015 addendum 5), so both variables are needed:

```
LEGAL_AI_ANSWER_MODEL=openrouter
LEGAL_AI_VERIFY_ENTAILMENT=1
OPENROUTER_API_KEY=...        # from .env.local, never committed
```

Re-deriving provision text after changing the extractor:

```
uv run --locked python scripts/derive_wa_provisions.py \
    tests/fixtures/wa_legislation/road_traffic_act_1974
```

## External review gate

The DeepSeek review gate ran six times and returned `BLOCKED` each time. Fifteen
findings in total, all accepted and fixed with tests:

| Round | Finding | Severity |
|---|---|---|
| 1 | `ENTAILMENT_SILENT_SKIP` | high |
| 1 | `VERIFIER_UNBOUNDED_PROVISION` | medium |
| 2 | `ENTAILMENT_VERDICT_PREFIX_ACCEPTANCE` | high |
| 2 | `REVIEW_GATE_SECRET_REDACTION_INCOMPLETE` | medium |
| 3 | `REDACTION_CORRUPTS_REVIEW_BUNDLE` | critical |
| 3 | `ENTAILMENT_SILENT_SKIP_WHEN_NO_PROVISION` | high |
| 3 | `INCOMPLETE_REVIEW_ENV_FILE_EXCLUDED` | medium |
| 4 | `REVIEW_GATE_SYMLINK_EXFILTRATION` | critical |
| 4 | `UNBOUNDED_MODEL_PROPOSITION_COUNT` | high |
| 4 | `UNHANDLED_OVERSIZED_QUESTION_VALIDATION_ERROR` | high |
| 5 | `LIVE_PROVIDER_WITHOUT_ENTAILMENT` | high |
| 5 | `UI_URL_SCHEME_NOT_VALIDATED` | medium |
| 5 | `REVIEW_GATE_SECRET_REDACTION_LOWERCASE_GAP` | medium |
| 6 | `REVIEW_GATE_PRIVATE_KEY_REDACTION_INCOMPLETE` | critical |
| 6 | `REVIEW_GATE_LOWERCASE_UNQUOTED_SECRET_GAP` | high |

Details in the ADR 0015 addenda. **The gate has not yet returned a
non-blocking verdict, so this branch is not ready to merge.** A third run is
required after these fixes.

### The one file the gate will not accept

The gate refuses to transmit any file whose name begins with `.env`, which is
correct and is not weakened here. To keep the change fully reviewable, the
complete `.env.example` diff is reproduced below — it is additive only, every
new value is blank except `LEGAL_AI_ANSWER_MODEL=mock`, and it contains no
credential:

```diff
+
+# Optional local-only external review gate configuration. Keep values blank.
+DEEPSEEK_API_KEY=
+DEEPSEEK_MODEL=
+
+# Read-only research API (ADR 0014, ADR 0015). Paths are relative to the repo.
+LEGAL_AI_WA_CORPUS_ROOT=
+LEGAL_AI_PROVISION_ROOT=
+LEGAL_AI_RESEARCH_AUDIT_LOG=
+LEGAL_AI_STATIC_DIR=
+
+# Answer model: "mock" (default) or "openrouter". A credential alone never
+# switches on a live provider; this must be set explicitly.
+LEGAL_AI_ANSWER_MODEL=mock
+LEGAL_AI_VERIFY_ENTAILMENT=
+
+# Live provider configuration. Keep values blank here; put real keys only in
+# .env.local, which is never committed.
+OPENROUTER_API_KEY=
+LEGAL_AI_OPENROUTER_MODEL=
+LEGAL_AI_OPENROUTER_BASE_URL=
```

Real keys live only in `.env.local`, which `.gitignore` excludes and which is
not part of any commit on this branch. A repository-wide scan for `sk-` token
shapes across every committed file returns nothing.

## Known limitations

- The corpus is two provisions of one WA Act. Almost every real question still
  refuses. Correct behaviour, and the main thing standing between this and
  usefulness.
- Derived text is a transformation of the official PDF. A reviewer should
  spot-check it against the official source; the parent digest cannot detect an
  extraction error.
- Level 3 uses the same provider as the answer model. A genuinely independent
  verifier would use a different one.
- `.env.example` in this commit also carries two blank DeepSeek lines staged
  earlier by the review-gate task.

## Rollback

```
git checkout main
git branch -D feat/phase-5-grounded-answer-api
```

No migration, no schema change, no persisted state, no modification to any
pre-existing module.

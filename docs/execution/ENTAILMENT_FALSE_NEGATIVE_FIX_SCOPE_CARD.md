# Scope Card — Entailment verifier false negatives

Branch: `fix/entailment-false-negatives`
Base ref: `chore/live-provider-smoke`
Date: 2026-09-09
Owner: Ali Rad

## Problem

Live adversarial run 2 (`docs/execution/LIVE_ADVERSARIAL_RUN_2.md`, family C)
showed the level-3 entailment verifier refusing correct, byte-exact grounded
answers. The identical grounded question against Sale of Goods Act 1895 s 14
refused 8 of 8 times: 4 as `ENTAILMENT_UNSUPPORTED` (the verifier ran and judged
a supported statement unsupported) and 4 as `ENTAILMENT_UNAVAILABLE`. This is a
false negative in the trust gate.

## Diagnosis (evidence-based, read-only investigation first)

- **Not a corpus defect.** s 14's derived text is complete and digest-verified
  (`s_14.txt` sha256 `7ff1db…40a3` equals the recorded digest; all five
  subsections present). `provisions.py` refuses any text whose digest mismatches,
  so a partial provision could not have been served.
- **Model-capability problem, aggravated by prompt.** The configured verify
  model (`deepseek-v4-flash`) is a reasoning model. Its chain-of-thought
  (a) overran `MAX_VERIFIER_TOKENS = 1024`, returning `finish_reason=length`
  with empty content and no verdict → spurious `ENTAILMENT_UNAVAILABLE`
  (observed traces exceeded 4,800 characters on s 6 / s 7 / s 17); and
  (b) reached `NOT_SUPPORTED` by treating a faithful summary that omits an
  exception/proviso as "unsupported" — a category error the prompt's
  "generalises beyond it / when in doubt NOT_SUPPORTED" wording encouraged.
- **Failure follows the model, not the provision.** The identical inputs judged
  `SUPPORTED` cleanly on two non-reasoning models. Per-provision false-negative
  measurement (deepseek-v4-flash, grounded statements, 3 runs each): s 14 3/3,
  s 7 3/3, s 6 2/3, s 17 1/3 NOT_SUPPORTED; the other 15 provisions clean.
  Aggregate 9/57 false negatives, 2/57 spurious unavailable. s 14 is not special.

## Change (this task)

`src/legal_ai/answering/verification.py` only:

1. Raise `MAX_VERIFIER_TOKENS` from 1024 to 8192 so a reasoning verify model's
   full trace plus the one-word verdict fit, removing the spurious truncation
   `ENTAILMENT_UNAVAILABLE`. Parsing is unchanged: the reply is still accepted
   only as an exact one-word verdict, so a decorated or over-budget reply still
   fails closed.
2. Reword `VERIFIER_SYSTEM_PROMPT` so "supported" means every claim the
   statement makes is borne out by the text, even if it omits an exception or
   qualification; `NOT_SUPPORTED` for anything the text does not say,
   contradicts, or a number/penalty/term/date/condition the text does not
   contain. This corrects the false negatives without loosening the gate.

## Non-goals / constraints

- Do not loosen or bypass the gate. Genuinely unsupported statements
  (contradictions, invented figures, invented conditions) must still refuse.
- Read-only on `src/` except the single verifier module above.
- Do not touch the scope boundary or the temporal-gap findings.

## Validation

- All 5 previously false-negatived grounded statements now `SUPPORTED` 3/3
  (15/15) against the live verify model with the new prompt and budget.
- Four genuinely unsupported statements (s 14 "abolishes all implied
  conditions"; s 55 "300 PU"; s 56 "within 24 hours"; s 7 invented waiver rule)
  still `NOT_SUPPORTED` (0 wrongly passed).
- Existing gate contract preserved: `test_hedged_or_decorated_verdict_refuses`
  (exact one-word verdict only) and all other `test_verification.py` cases pass.

## Cost and latency of the budget change (measured 2026-09-09)

The gate flagged the 1024 -> 8192 `MAX_VERIFIER_TOKENS` change as unmeasured.
Measured against the live verify model (`deepseek-v4-flash`):

- **The 8192 ceiling is almost never reached.** Actual verifier completion
  tokens on 10 grounded statements averaged ~90-160 (max 687 under the old cap,
  277 under the new) — well below even the old 1024. Raising the ceiling adds no
  steady-state token spend; it only prevents intermittent truncation on
  long-reasoning cases. Controlled A/B (same prompt, budget 1024 vs 8192) showed
  no cost or latency increase (the new arm was marginally faster, within
  reasoning-model run-to-run noise).
- **Per-answer cost did not rise.** OpenRouter answer-side cost measured
  $0.0038/answer over 10 grounded answers; the DeepSeek verifier adds ~690
  prompt + ~100 completion tokens per proposition verified (sub-$0.001 at flash
  rates). Total stays around the ~1 cent/answer round-2 baseline — it does not
  double.
- **Verifier latency per call ~1.5-2.6 s**, unchanged by the budget. End-to-end
  per-answer latency is dominated by proposition count (one verifier call per
  proposition), not the budget.

### Residual finding (honest scope limit — not fixed here)

Isolated verification of grounded statements is fixed (15/15 previously-failing
statements now SUPPORTED). But **end-to-end, multi-proposition answers on
exception-heavy provisions can still refuse.** The live answer model returns up
to 4 propositions for s 7 and s 14; the pipeline refuses the whole answer if any
one fails (`_run_level_three`: "one failure still refuses everything"). Two
causes compound: (a) residual per-proposition verifier nondeterminism, and
(b) genuinely imperfect propositions — e.g. an s 7 proposition rephrased
"whether in an owner-driver contract **and** whether in writing or not" as
"...**or not**", which the verifier correctly declined. This is a separate issue
from the false negatives fixed here and is left for the backlog item below.

## Backlog (record only — do NOT build in this task)

**One future task: surface "true but partial" in the answer text rather than
refusing or staying silent.** Two findings are the same class of problem:

1. **Omitted statutory exceptions.** This fix makes a statement SUPPORTED when it
   accurately restates part of a provision but omits an exception or proviso the
   text also contains (e.g. s 14(3) merchantable quality without the "if the
   buyer has examined the goods" proviso). Technically supported, legally
   incomplete.
2. **Unflagged temporal/version gap** (from `LIVE_ADVERSARIAL_RUN.md` T1 and
   `LIVE_ADVERSARIAL_RUN_2.md` family A): a past-dated question is answered from
   the current snapshot with no caveat in the answer text.

Both are "true but partial": correct as far as they go, but the answer text does
not tell the reader what was left out or that the currency may not match. The
future work is to **surface omitted exceptions and version gaps in the answer
text** (a caveat/annotation), rather than either refusing the answer or leaving
the omission silent. Also worth considering: per-proposition partial answers so
one imperfect proposition does not sink an otherwise grounded answer.

## Owner decision — defer `partial-omission-legal-completeness`

- Status: Accepted (deferred, not dismissed)
- Date: 2026-09-09
- Owner: Ali Rad

### Finding

The DeepSeek review gate raised a medium-severity critical finding,
`partial-omission-legal-completeness`, against the reworded
`VERIFIER_SYSTEM_PROMPT`: the prompt now marks a faithful but partial summary as
SUPPORTED even when it omits an exception, proviso, or qualification present in
the provision, so level 3 can pass an answer that is technically supported but
legally incomplete, without a caveat. The gate exited non-zero. The finding is
correct and stands.

### Decision

The owner accepts the finding and defers it. The prompt change is retained as
specified for this task: correcting the false negatives required treating an
accurate partial summary as supported, and the alternative (refusing any
statement that omits an exception) is the false-negative behaviour this task was
commissioned to remove. This is a deliberate, recorded owner decision made by a
person — not a gate bypass, an override of the review, or an unreviewed change.
The gate's judgement is accepted as right; only its timing is deferred.

### What closes it

The deferral is closed by the follow-up task on branch
`feat/per-proposition-answers`: verifying and reporting each proposition on its
own, so a proposition that omits a statutory exception can be surfaced as a
withheld/partial part of the answer with its reason, rather than either silently
passing or sinking the whole answer. The related temporal/version-gap surfacing
remains in the backlog item above. Until that work lands, the finding remains
open and recorded here, not resolved.

## Definition of done

ruff, ruff format --check, mypy, pytest, then the DeepSeek review gate.
Adds an offline guard test (`tests/answering/test_verification_intent.py`)
pinning the prompt semantics with recorded verifier replies.

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

## Definition of done

ruff, ruff format --check, mypy, pytest, then the DeepSeek review gate.

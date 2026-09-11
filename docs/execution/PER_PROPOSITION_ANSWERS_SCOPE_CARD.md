# Scope Card — Per-proposition answers

Branch: `feat/per-proposition-answers`
Base ref: `fix/entailment-false-negatives`
Date: 2026-09-09
Owner: Ali Rad

## Problem

Level-3 entailment was all-or-nothing: one proposition failing refused the whole
answer (`GroundedAnswerService._verify` returned a single refusal code, and
`answer` refused on it). The richer the provision, the more propositions an
answer carries, and the more likely one fails — so the most complex provisions
refused end to end. Owner-Drivers s 7 and Sale of Goods s 14, each answered live
with four propositions, refused 3/3 and repeatedly (see
`LIVE_ADVERSARIAL_RUN_2.md` family C and the residual finding recorded in
`ENTAILMENT_FALSE_NEGATIVE_FIX_SCOPE_CARD.md`). That is backwards from what a
user needs.

## Change

Make the unit of the level-3 decision one proposition instead of the whole
answer, without weakening any per-proposition check:

- `GroundedAnswerService` grades each proposition independently
  (`_grade_each` -> per-proposition `_Verdict`), then assembles the result
  (`_decide`): supported propositions are kept with their citations; an
  unsupported or unverifiable one is dropped and recorded as withheld with its
  reason; at least one survivor yields a partial `GroundedAnswer`; no survivor
  refuses the whole answer exactly as before.
- New domain types `WithheldReason` (`UNSUPPORTED` / `UNVERIFIED`) and
  `WithheldProposition`; `GroundedAnswer` gains a `withheld` tuple (default
  empty, so a complete answer is unchanged).
- API: `AnswerBody` gains `partial: bool` and `withheld: tuple[WithheldBody]`.
  `WithheldBody` carries the pinpoint and reason only.

## Non-goals / constraints

- **Do not weaken any per-proposition check.** A proposition is kept only on a
  clean SUPPORTED verdict; UNSUPPORTED and any verifier fault/outage
  (`VerifierUnavailable` or any exception) withhold that proposition. A verifier
  fault is confined to the proposition it graded and never reads as a pass and
  never as a verdict for another proposition. If nothing survives, refuse; if
  any proposition was unverifiable in that case, prefer `ENTAILMENT_UNAVAILABLE`
  over `ENTAILMENT_UNSUPPORTED` so an outage never reads as a clean refusal.
- **Never republish an unverified statement.** A withheld statement failed
  entailment and is exactly the confident-but-wrong content the pipeline exists
  to keep out of an answer. `WithheldProposition` retains the statement for
  auditing, but the API renders pinpoint and reason only; `render_answer` never
  copies the statement into the response. Guarded by a test.
- Read-only on the rest of `src/`.

## Relationship to the deferred finding

This closes the mechanism half of `partial-omission-legal-completeness`
(deferred by owner decision 2026-09-09): the pipeline can now surface part of an
answer as withheld rather than all-or-nothing. Fully surfacing an omitted
statutory exception (a supported-but-incomplete proposition) and the
temporal/version gap in the answer text remains the backlog item in the
entailment fix scope card.

## Tests (written first, from the real s 7 / s 14 cases)

`tests/answering/test_per_proposition.py`:
- one unsupported proposition is dropped, the other three answer (s 7 and s 14);
- an unverifiable proposition is withheld as `UNVERIFIED` while the rest answer;
- a wholly unsupported answer refuses `ENTAILMENT_UNSUPPORTED`;
- a wholly unverifiable answer refuses `ENTAILMENT_UNAVAILABLE`;
- all-supported returns every proposition with no withheld;
- the API renders `partial`, pinpoint, and reason, and never the withheld
  statement text.

Live confirmation (fresh instance, live chain): s 7 now ANSWERED partial with 3
kept and 1 withheld (`UNSUPPORTED/section 7`); s 14 now ANSWERED. Both previously
refused end to end.

## Definition of done

ruff, ruff format --check, mypy, pytest, then the DeepSeek review gate.

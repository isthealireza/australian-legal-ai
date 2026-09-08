# WF5 draft: ingress-only conflict detection — both suites pass, NOT published

**WF5 is not published.** Draft `bc38f138`, live still `4101d42f`. Verified fresh after the
last edit. Production continues to run the previous thread-first version.

| Suite | Execution | Result |
|---|---|---|
| Thread-first + sender-verification + replay regression | **314** | **29 / 29**, `safe_to_publish: true` |
| Guarded replay write test (real sheets) | **313** | **FULLY_PROVEN** |

Baseline check first, as you asked: before any edit, `versionId` and `activeVersionId` were
both `4101d42f` with 44... 43 nodes. No half-applied or lost change from any earlier
connection loss. Everything below was applied on top of that confirmed state.

## The schema blocker, and what you authorised

Of your six stable ingress fields, an INBOUND row in `Communications` stored only four:
`provider_message_id`, `thread_id`, `subject`, `received_at`. It did **not** store the
sender — the `recipient` column holds *our* address on inbound rows — and did not store the
body or any digest of it. So `same message id + same raw message → ALREADY_RECORDED` was
not implementable: there was nothing to compare against.

You authorised one new column. Added by a single API write to `Communications!R1`:
`updatedCells: 1`, `updatedRange: Communications!R1`, header count 17 → 18. No row appended,
no existing cell touched.

`ingress_fingerprint` holds a digest over all six fields, not the raw body — the body stays
in Gmail rather than being copied into the register.

## Fingerprint behaviour (tested locally, 8/8, before anything was applied)

Stable under: whitespace reflow in the body, and a changed display name on the same address.
Changes on: body, subject, sender address, thread id, provider timestamp.

## Applied to the WF5 draft

1. **`Build Reply Context`** — ingress-only conflict detection. Compares `provider_message_id`, `thread_id`, sender, subject, raw body, provider timestamp. Never `summary`, never `classification`, never a regenerated `communication_id`.
2. **`communication_id` is now `COM-<provider_message_id>`** — a pure function of the message id, so it is created once and identical on every replay. A stored value always wins.
3. **`Log Inbound`** persists `ingress_fingerprint` and takes `communication_id` from the resolver.
4. **New `Log New Inbound`** — one deterministic `NEW_INBOUND` event per accepted message, keyed `EVT-INBOUND-<pmid>`, on the accept path only. Chain verified: `Log Inbound → Log New Inbound → Create Next Action?`.
5. **`Log Unverified Sender`** → `appendOrUpdate` on `event_id`, using the resolver's deterministic id. Replay events keyed `EVT-REPLAY-<pmid>`, conflicts `EVT-REPLAY-CONFLICT-<pmid>` — separate ids, so a conflict never overwrites a benign ignore record, and reprocessing the same conflict updates one row instead of appending.
6. **Telegram** now has a distinct IDEMPOTENCY_CONFLICT message stating that nothing was changed and asking you to compare the two deliveries.

Events is treated as a record of system decisions, per your instruction. No transport-attempt
counting anywhere.

## Two defects I introduced, caught by verification before publishing

**1. A wall clock inside a fingerprint input.** `Match Reply to Matter` fell back to
`new Date().toISOString()` when a message carried no date header. Since `received_at` feeds
the fingerprint, an ordinary retry of an undated message would have produced a different
fingerprint and been reported as `IDEMPOTENCY_CONFLICT` requiring human review — exactly the
false-conflict class the design exists to avoid. Fixed: an absent provider timestamp is now
empty, not "now". Regression added as **X5 / X5b**, both PASS: the undated message is
accepted, then replayed identically and resolves `ALREADY_RECORDED` with
`stored_fingerprint == fingerprint` (`ING-4d8a43a1-36`) and no human review.

**2. A clock-derived `communication_id` leaking to Telegram.** `Validate Reply JSON`
re-assigned `communication_id: 'COM-' + <wall clock>` *after* spreading the resolver output.
`Log Inbound` dodged it by reading the resolver explicitly, but `Build Reply Notice` read
`Validate Reply JSON`, so the Telegram notice reported an id that **did not exist in the
Communications sheet**, and two deliveries would have shown two different ids. The
assignment is removed; the deterministic value now flows through the spread. That was the
only change to that node — 0 `new Date()` references remain in it.

Neither defect was caught by either suite as written. Both were found by structural review
of the draft. That is worth noting about the method: the suites test the resolver, not the
nodes feeding it.

## Suite 314 detail — 29 cases

Matching suite (10): C1, C2, C3, C4, C6, C6b, C7, C8, C9, C10 — all PASS.
Replay suite (13): X3, X5, X5b, R1–R6, X1, X1b, X1c, X2, X4 — all PASS.
Invariants (6): E1 deterministic accept event id, D1 determinism, A1 every replay outcome
carries a deterministic audit event id, A2 nothing mutates on blocked/already-recorded/
conflict, A3 no replay outcome reaches the classifier.

Behaviour confirmed exactly as you specified:

```
same pmid + same raw message      -> ALREADY_RECORDED, no classifier, no mutation   (R1-R6, X4, X5b)
same pmid + different raw message -> IDEMPOTENCY_CONFLICT, human review, no mutation (X1, X1b, X1c, X2)
different pmid                    -> NEW_INBOUND, continues to classification        (C1, C2, C7, X5)
```

X4 is the one worth calling out: a whitespace-reflowed body resolves `ALREADY_RECORDED`, not
a conflict. Without that, every mail client that rewraps text would raise a false conflict.

## The gap I am not papering over

**The fingerprint round-trip has not been proven against a real sheet.** Suite 314 proves
the resolver's logic; suite 313 proves the guarded write pattern against real sheets — but
313 predates this correction and still compares `communication_id`, `summary` and
`classification` (visible in its own `conflict_fields_r2`). So nothing yet demonstrates that
`Log Inbound` actually writes `ingress_fingerprint` into the live column and that the
resolver reads that value back on a later delivery.

That integration is the last untested link. Closing it means either updating the guarded
harness to the ingress fields and pointing it at a throwaway sheet with an
`ingress_fingerprint` column, or one controlled live replay after publishing. I would do the
former before publishing rather than the latter after.

Also unchanged: `X3` means every INBOUND row written before today has no fingerprint, so a
replay of any pre-existing message resolves `FINGERPRINT_NOT_RECORDED` → conflict → human
review. Fail-closed and correct, and currently vacuous because `Communications` has no data
rows at all.

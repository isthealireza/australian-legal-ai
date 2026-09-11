# Replay idempotency — corrected verdict

```
PARTIAL — Communication and action deduplication proven; full replay idempotency not proven.
```

Your correction was right on all four points. Execution **296**, `QA - Replay Write Test`
(`xb9hgu2rpMjw9CUt`), own throwaway spreadsheet `1bG8sRdI6mkOjfbaCkgc4WA75INYT4GAz3jxU1VcEcPI`.
WF5 and production untouched.

## Against your expected result

| Expected | Measured | Result |
|---|---|---|
| Communication rows: unchanged | 2 → 2 | **MET** |
| Original Communication content: unchanged | all 5 fields replaced | **NOT MET** |
| Actions: unchanged | 1 → 1 | **MET** |
| Matter: unchanged on replay | `FIRST-RUN-STAMP` → `REPLAY-RUN-STAMP` | **NOT MET** |
| Inbound event: no duplicate | 2 → 3 rows | **NOT MET** |

## 1 and 2. Same key, deliberately different replay payload

Key `MAT-QA-001|MSG-QA-1` both times. `rows_matching_key: 1`, rows 2 → 2.

```
after first : communication_id=COM-FIRSTRUN  | subject=Re: QA replay test
              | summary=first delivery | classification=ACKNOWLEDGEMENT
              | received_at=2026-08-20T05:00:00.000Z
after replay: communication_id=COM-REPLAYRUN | subject=Re: QA replay test SECOND DELIVERY
              | summary=replay delivery with deliberately different content
              | classification=OFFER | received_at=2026-08-20T06:00:00.000Z
```

`content_fields_changed_by_replay: communication_id, subject, summary, classification,
received_at` — **every content field was overwritten.**

This is not a tuning problem, it is what the operation is. `appendOrUpdate` means append if
no match, **update** if match. It can never be a no-op. Note the severity: `classification`
went from `ACKNOWLEDGEMENT` to `OFFER`. A replay carrying a different classification would
silently rewrite the legal characterisation of the correspondence on the surviving row.

## 3. Matter timestamp at all three stages

```
before first run : SEED-STAMP
after first run  : FIRST-RUN-STAMP
after replay     : REPLAY-RUN-STAMP
```

The matter is mutated on replay. One row throughout, so no duplication — but `status`,
`updated_at` and `last_activity_at` are rewritten each time, because `Touch Matter (Reply)`
matches on `matter_id`, which is stable by design.

## 4. Event counts and types per run

```
after first run : 2 rows — SEED, INBOUND_REPLY_DUPLICATE
after replay    : 3 rows — SEED, INBOUND_REPLY_DUPLICATE, INBOUND_REPLY_DUPLICATE
```

Both runs created an event row. Two identical `INBOUND_REPLY_DUPLICATE` entries, confirming
your point directly: `append` with `matchingColumns: []` cannot deduplicate, and a random
`event_id` makes each row distinct rather than collapsible.

## 5. Item counts — multiplication absent

```
comms before        : 1     actions after first : 2
comms after first   : 2     actions after replay: 2
comms after replay  : 2     matters before      : 1
events after first  : 2
```

**`item_count_comms_after_replay: 2`** — the figure that was missing from 295. All counts
equal actual row counts, so no read emitted duplicated items and no write ran more than
once. (`actions` shows 2 because the seed action row is counted alongside the test action;
only 1 matches the action key.)

## What this means for production, stated precisely

The three failures are all at the **write layer**. In production a replay never reaches
those nodes, because the `DUPLICATE` decision blocks the branch upstream — proven separately
in exec 288, R1–R4, where a replay yields `write_log_inbound: false`,
`write_append_action: false`, `write_touch_matter: false`.

So the accurate statement is: **the decision layer provides replay idempotency; the write
layer provides duplicate-row protection only.** They are not redundant, as I previously
implied. The write layer is a partial backstop: it prevents duplicate rows but not
overwrites, matter mutation, or duplicate audit events. If the decision gate were ever
bypassed or removed, replay protection would be materially weaker than it looks.

## What would make the write layer a true no-op

Read-then-skip: query for the key first, and if a row exists, do not write at all. In n8n a
Code node returning zero items skips the downstream write entirely. That converts replay
from *update* into *nothing*, which is what you asked for.

Applied to the three failures:

- Communications: guard `Log Inbound` on an existing key → content preserved
- Matters: guard `Touch Matter (Reply)` on the same decision → no mutation
- Events: either a deterministic `event_id` with `appendOrUpdate` matching on it, or accept duplicates deliberately

I have not built this. It changes WF5, which you have not authorised. I can build it as an
isolated demo on a throwaway sheet first, to prove the no-op empirically before anything is
proposed for WF5 — say the word.

One caveat on the Events case, unchanged from last pass: deduplicating an audit log destroys
the count of how many times something was attempted. For `INBOUND_REPLY_DUPLICATE`
specifically, "this arrived four times" may be the fact you want to keep.

## Housekeeping

Runs 293–296 each created a spreadsheet in your Drive titled
`QA Replay Write Test <timestamp>`, containing only synthetic `MAT-QA-001` data. Four now.
Safe to delete; I have kept them as the evidence.

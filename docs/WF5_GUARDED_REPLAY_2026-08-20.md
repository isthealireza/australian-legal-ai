# Guarded replay test — FULLY_PROVEN

```
verdict: FULLY_PROVEN
```

`QA - Guarded Replay Test` (`c6YPmuWf3cevjZ3r`), execution **301**, `success`.
Own throwaway spreadsheet `1OUWQQOf8u_u2_pmLt_6eUdVUJRelAZP9gtY_MQTJ59c`.
**WF5 was not modified in this pass. Production untouched. `dry_run` untouched.**

## Against your expected result

| Expected | Measured | |
|---|---|---|
| Communication content: unchanged on replay | `content_fields_changed_by_replay: (none)` | **MET** |
| Actions: unchanged on replay | 1 → 1 | **MET** |
| Matter: unchanged on replay | `R1-STAMP` → `R1-STAMP` | **MET** |
| First inbound event: one | `new_inbound_events_after_r1: 1`, `duplicate_labelled_events_after_r1: 0` | **MET** |
| Replay event: one explicitly named replay-ignored event | `INBOUND_REPLAY_IGNORED_CONFLICT`, count 1 | **MET** |
| Verdict | `FULLY_PROVEN` | **MET** |

## Decisions

```
decision_r1: NEW_INBOUND            allow_mutations_r1: true
decision_r2: IDEMPOTENCY_CONFLICT   allow_mutations_r2: false
decision_r3: IDEMPOTENCY_CONFLICT   allow_mutations_r3: false
requires_human_review_r2: true
conflict_fields_r2: communication_id, subject, summary, classification, received_at
```

## Content preserved through both replays

```
after R1: communication_id=COM-FIRSTRUN | subject=Re: QA replay test | summary=first delivery
          | classification=ACKNOWLEDGEMENT | received_at=2026-08-20T05:00:00.000Z
after R2: identical
after R3: identical
```

The replay payload carried `COM-REPLAYRUN`, a different subject, summary,
`classification=OFFER` and a later timestamp. None of it landed. `COM-FIRSTRUN` survived.

Rows: 2 → 2 → 2. Actions: 1 → 1. Matter stamp: `R1-STAMP` after R1 and still `R1-STAMP`
after R2 — the second `Touch Matter` never ran.

## Events

```
after R1: 2 rows — SEED, NEW_INBOUND
after R2: 3 rows — SEED, NEW_INBOUND, INBOUND_REPLAY_IGNORED_CONFLICT
after R3: 3 rows — SEED, NEW_INBOUND, INBOUND_REPLAY_IGNORED_CONFLICT
```

Round 3 replayed the identical message again and produced **no fourth row**. The replay
event id is `EVT-REPLAY-MSG-QA-1`, derived from the provider message id, and the event write
is `appendOrUpdate` matched on `event_id` — so repeated replays update that one audit row
instead of piling up. This is the deterministic replay event you asked for, and round 3
exists specifically to prove it does not multiply.

`item_count_comms_after_r2: 2` — no item multiplication.

## Your point 4: the first-run duplicate label was my test's fault

You were right to demand an explanation, and the answer is that it was a defect in **my
fixture**, not in WF5. In the previous test I hardcoded `event_type:
'INBOUND_REPLY_DUPLICATE'` on both event writes, because I was simulating the node that
logs duplicates. That mislabelled the first delivery. It told you nothing about WF5 and it
should not have shipped in a report.

Worth being precise about what WF5 actually does today: on a first delivery it writes **no
Events row at all** — it writes Communications, Actions and Matters. Only the blocked and
duplicate branch writes to Events. So requirement 7 is a genuine behaviour change, not a
relabelling: `NEW_INBOUND` would be a new audit row that does not currently exist.

## What this means for WF5 specifically

Your seven-point fix maps onto WF5's published version (`4101d42f`) as follows:

| Fix | State in WF5 today |
|---|---|
| 1. Read the key before any mutation | **present** — `Load Comms (Reply)` feeds the resolver |
| 2. Return `ALREADY_RECORDED` if the key exists | **present** — that exact basis string |
| 3. Skip `Log Inbound`, `Append Next Action`, `Touch Matter` | **present** — DUPLICATE fails the `decision === 'ACCEPT'` gate |
| 4. Preserve the original Communication row | **present as a consequence of 3** |
| 5. `IDEMPOTENCY_CONFLICT` on same key with different content | **absent** — WF5 compares only `provider_message_id`, never content |
| 6. Separate deterministic replay event | **absent** — `Log Unverified Sender` uses a random `event_id` and `append` |
| 7. First delivery produces `NEW_INBOUND` | **absent** — no Events row is written on a first delivery |

So the delta is items **5, 6 and 7**. Items 1–4 already hold, which is why exec 288 showed
a replay producing no writes. What exec 301 adds is proof that 5, 6 and 7 work as designed
and that the combination yields true no-op replay rather than the overwrite behaviour
exec 296 exposed.

## Not done, awaiting your authorisation

I have not applied any of this to WF5. Doing so means:

- adding a content comparison to the resolver and a third decision value `IDEMPOTENCY_CONFLICT` with `requires_human_review`
- changing `Log Unverified Sender` from `append` with a random `event_id` to `appendOrUpdate` on a deterministic one, for replay events only
- adding a `NEW_INBOUND` event write on the accept path, which is a new row type in your Events tab

The third one changes what your Events log contains on every normal reply, so it is worth a
deliberate decision rather than my judgement. And the caveat I have raised twice still
stands: making replay events collapsible destroys the count of how many times a message
arrived. `INBOUND_REPLAY_IGNORED_CONFLICT` occurring four times may be exactly the fact you
want visible. If so, keep `append` for that one and accept the duplicate rows knowingly.

## Housekeeping

Runs 293–296 and 301 each created a spreadsheet in your Drive titled `QA Replay Write Test`
or `QA Guarded Replay Test` plus a timestamp. Five now, all containing only synthetic
`MAT-QA-001` data. Kept as evidence; safe to delete.

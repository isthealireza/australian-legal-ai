# Replay write test — observed behaviour

Check 4 is now **PROVEN** for Communications and Actions. Two of the seven metrics show
behaviour you should decide about: the matter row is overwritten, and event rows duplicate.

Isolated: `QA - Replay Write Test` (`xb9hgu2rpMjw9CUt`). It creates its **own throwaway
spreadsheet** on each run. Your production spreadsheet, WF5 and `dry_run` were not touched.

Runs: 293 failed (see Corrections), 294 passed, **295 is the record** — `success`,
spreadsheet `1ZBM3CbDYWWKHZrFkXOmPopd5ewNJz7QRm3mO0u66I3g`.

## The seven metrics, measured

| # | Metric | Value |
|---|---|---|
| 1 | Comms rows before first run | **1** (the synthetic seed) |
| 2 | Comms rows after first run | **2** |
| 3 | Comms rows after replaying the same message | **2** |
| 4 | Rows matching the idempotency key | **1** |
| 5 | Actions after first run | **1** |
| 6 | Actions after replay | **1** |
| 7 | Matter rows / matter mutation | **1 row**, `updated_at` = `REPLAY-RUN-STAMP` |
| 7 | Event rows | **3** total — seed plus **2** created by two appends |

Derived: `comms_rows_created_by_first_run: 1`, `comms_rows_created_by_replay: 0`,
`actions_created_by_replay: 0`. Verdict field: **PROVEN**.

Against your expected result:

```
First run: one Communication row and one action     -> MET (1 row, 1 action)
Replay: no additional Communication row and no additional action -> MET (0, 0)
```

## Two findings that are not in the pass criteria

**The matched row's contents were overwritten.** `surviving_communication_id:
COM-REPLAYRUN`, `surviving_summary: replay delivery`,
`row_content_overwritten_by_replay: true`. The replay created no new row, but it replaced
the first run's values in the row it matched. So `appendOrUpdate` is idempotent in **row
count** and not idempotent in **row content**. This is the `communication_id` volatility I
flagged as a theoretical note last pass — it is now empirically confirmed. It matters for
audit: the surviving row records the last delivery, not the first.

**The matter row was mutated.** One row, but `updated_at` holds `REPLAY-RUN-STAMP`, so the
second write landed. `Touch Matter (Reply)` matches on `matter_id`, which is stable across
replays by design, so a replay that reached it would move `status`, `updated_at` and
`last_activity_at` again. No duplicate row; a real mutation.

**Event rows duplicated: 2 appends produced 2 rows.** This is the gap you identified.
`append` with `matchingColumns: []` cannot deduplicate, and a random `event_id` makes each
row distinct rather than collapsible.

None of these three break the check you asked for, because in production a replay never
reaches these nodes — the `DUPLICATE` decision blocks the branch upstream (exec 288,
R1–R4). What this test proves is that the **second, independent layer** also holds for
Communications and Actions. The two layers are now each proven separately:

- decision layer: `QA - WF5 Reply Policy v2`, exec 288, replay produces no write
- write layer: this test, exec 295, a forced double write produces one row

## Corrections to my own work

**Run 293 failed and its numbers would have been fiction.** Two faults, both mine:

1. `append` with `mappingMode: defineBelow` requires a `columns.schema` array. `appendOrUpdate` tolerated an empty one; `append` does not. Fixed by feeding the Events writes from a Code node with `autoMapInputData`.
2. Worse: **item multiplication.** Each read emits one item per row, and every downstream write then ran once per item. `Count Matters` returned 20 identical items. Had the run completed, the counts would have been meaningless while looking plausible. Fixed with `executeOnce: true` on all 20 Sheets nodes.

**Run 294 reported metric 5 as the string `see q6 note`, not a number.** Actions after the
first run were never counted, only after the replay. I could have inferred 1 — the
after-replay count is 1 and `appendOrUpdate` never deletes — but that is inference, and you
asked for a measurement. Added `Count Actions After First` and re-ran as 295, which
measures it directly: **1**.

## What this still does not prove

The seed row is synthetic and the write nodes are copies configured to match production,
not the production nodes themselves. Equivalence rests on the configuration comparison in
the previous pass (operation, matchingColumns, mapped key, live column) rather than on
running WF5. Running WF5's own `Log Inbound` would require WF5 to execute against a real
Gmail item and a real matter.

Also unchanged: the WF3 vision branch, `Log Send Intent`, `Mark Send Failed`, and WF4 gate
checks 6.5–6.7 remain untested.

## Housekeeping

Each run creates a throwaway spreadsheet in your Drive, titled
`QA Replay Write Test <timestamp>`. Runs 293, 294 and 295 left three of them. They contain
only synthetic `MAT-QA-001` data and can be deleted whenever you like — I have not deleted
them, since they are the evidence for these numbers.

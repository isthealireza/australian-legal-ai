# WF5 real-sheet round trip and structural lint

```
Resolver logic:          PASS   (exec 316, 29/29)
QA regression suite:     PASS   (exec 316, matching 10/10, replay 13/13, invariants 6/6)
Production integration:  PASS   (exec 315, ROUND TRIP PROVEN, 8/8 checks)
Structural linter:       PASS   (5/5 checks, 0 FAIL, 0 WARN)
Draft verified:          cdb05a7e-07ce-48b5-99b9-d37192f33d40
Live version:            4101d42f-8492-4bff-8288-cb56138f1cb4  (unchanged)
Safe to publish:         YOUR CALL — one residual, described at the end
```

## Round trip: `QA - Ingress Round Trip` (`XevQwFviJHUobw0U`), execution 315

Own throwaway spreadsheet `1Zcz9h0bK0FtQYAK8PAFWQ-LiKK4Z1evR39_B7oscLlg`.
`comms_header_count_after_seed: 18` — the throwaway tab carries the current schema
including `ingress_fingerprint`.

| Your step | Measured | |
|---|---|---|
| 1. Throwaway sheet, current 18-column schema | header count 18 | ✓ |
| 2. Process a first inbound message | `decision_r1: ACCEPT` | ✓ |
| 3. `ingress_fingerprint` written to column R | `fingerprint_stored_in_sheet: ING-a7728903-20` | ✓ |
| 4. Read the stored row back | read back via `Read Comms 2` | ✓ |
| 5. Replay the same message | round 2 | ✓ |
| 6. Resolver reads the stored fingerprint, returns ALREADY_RECORDED | `fingerprint_read_back_by_r2: ING-a7728903-20`, `decision_r2: ALREADY_RECORDED` | ✓ |
| 7. No classifier, action, matter update or Communication overwrite | `content_changed_by_r2: (none)`, comms 2→2, actions 2→2, matter `R1-STAMP`→`R1-STAMP` | ✓ |
| 8. Replay same message id, changed body | round 3, `fingerprint_r3_incoming: ING-05bdd359-47` | ✓ |
| 9. IDEMPOTENCY_CONFLICT, human review, no mutation | `decision_r3: IDEMPOTENCY_CONFLICT`, `requires_human_review_r3: true`, `content_changed_by_r3: (none)` | ✓ |
| 10. `communication_id` is `COM-<pmid>` everywhere incl. Telegram | all four sites `COM-MSG-RT-1`; notice `"Logged as: COM-MSG-RT-1"` | ✓ |

The fingerprint genuinely round-tripped: written by the write node into column R, read
back off the sheet by the next round, and matched. Two different fingerprints for the two
different bodies (`ING-a7728903-20` vs `ING-05bdd359-47`), which is what separates
ALREADY_RECORDED from IDEMPOTENCY_CONFLICT.

Event ids, deterministic and separated by decision:
`EVT-INBOUND-MSG-RT-1` → `EVT-REPLAY-MSG-RT-1` → `EVT-REPLAY-CONFLICT-MSG-RT-1`.
Event types accumulated `SEED, NEW_INBOUND` → `+ INBOUND_REPLAY_IGNORED` →
`+ INBOUND_REPLAY_IGNORED_CONFLICT`.

**Design note worth stating:** both replay rounds have a real overwrite node wired to their
accept branch (`Write Comms R2` / `Write Comms R3`, which would stamp
`COM-SHOULD-NOT-HAPPEN` and `R2 OVERWROTE THE ROW`). Neither fired. Without those the "no
overwrite" result would only prove that I didn't wire an overwrite, not that the gate stopped one.

## Structural linter

Delivered as `wf5_structural_lint.py`. Run: `python3 wf5_structural_lint.py wf5.json`,
where the JSON is a `get_workflow_details` dump. Exit 1 on any FAIL.

```
L1  no clock-based communication_id                         PASS
L2  no clock-based idempotency key                          PASS
L3  no clock fallback for a missing provider timestamp      PASS
L4  no downstream overwrite of a deterministic identifier   PASS
L5  no write node relying only on cached schema             PASS

FAIL 0   WARN 0   REVIEW 0
```

L5 initially reported two WARNs — `Log New Inbound` and `Log Unverified Sender` were writing
ten Events columns with an empty `columns.schema`, so both relied on runtime header
resolution rather than a declared contract. Both now carry the full ten-column schema
matching the live header row, and L5 is clean.

L5 checks four things beyond the schema being populated: that every mapped column exists in
the live sheet, that no cached schema entry names a column the sheet lacks, that an
`appendOrUpdate` has `matchingColumns`, and that whatever it matches on is a column it
actually writes. The live header sets are hardcoded from the sheet reads (execs 291, 311),
not from n8n's cache — that distinction is the whole point of the check.

**Why this is a script and not an n8n workflow.** Reading workflow definitions needs an
`n8nApi` credential, which does not exist on this instance. It is the same blocker that left
QA Autopilot's self-repair dead (`AUTOPILOT_BLOCKER: n8nApi credential not yet created`).
Create that credential and this becomes a scheduled workflow that lints WF1–WF5 and reports
to Telegram; until then it runs outside n8n against a dump.

## The one residual

The round trip exercises **a copy** of the resolver in a QA workflow against a real sheet
with the real schema and the same node configuration pattern. It does not execute WF5's own
nodes. Nothing short of WF5 running against a real Gmail delivery closes that last inch, and
that cannot happen before publishing.

So the choice is: publish and let the first genuine reply be the final proof, with the
linter and both suites as the safety net — or leave it unpublished. Everything I can prove
without running WF5 itself is now proven. `dry_run` remains `"true"` either way, so nothing
can leave the account regardless.

# WF5 structural lint — fresh dump

Read-only. The linter opens a JSON file and prints; it makes no API calls and cannot
modify, publish or activate anything. WF5 was not modified, published or activated.

Input: `/home/claude/lint/wf5.json`, 161,365 bytes, the fresh `get_workflow_details`
dump. Definition read from **`d["workflow"]`** — confirmed before running:

```
top-level keys      : ['workflow', 'triggerInfo']
nodes under workflow: 44
nodes at top level  : 0        (the definition is not at the top level)
```

## Result

```
workflow      : 5 - Inbound Replies and Daily Supervisor  (zDLoMgW42jUm25Q4)
versionId     : cdb05a7e-07ce-48b5-99b9-d37192f33d40   <- draft
activeVersion : 4101d42f-8492-4bff-8288-cb56138f1cb4   <- live
published     : NO, draft differs from live
nodes scanned : 44        code nodes: 9        sheet writers: 8

L1  no clock-based communication_id                      PASS
L2  no clock-based idempotency key                       PASS
L3  no clock fallback for a missing provider timestamp   PASS
L4  no downstream overwrite of a deterministic identifier PASS
L5  no write node relying only on cached schema          PASS

FINDINGS: none. 0 FAIL, 0 WARN, 0 REVIEW.
exit=0
```

**There are no findings, so there is nothing to report per finding.** Rather than leave it
there, see the negative control below — a clean pass is worthless if the checks cannot fire.

## Negative control — proof the checks are not vacuous

I copied the dump to `wf5_negative.json` and reintroduced the exact defects that were real
in this workflow earlier today, plus two synthetic schema faults. `wf5.json` itself was not
touched. Every check fired, with the five fields you asked for:

```
L1 FAIL   L2 FAIL   L3 FAIL   L4 REVIEW   L5 FAIL      TOTALS  FAIL 6  WARN 1  REVIEW 1   exit=1
```

| # | Severity | Check | Node | Path | Evidence |
|---|---|---|---|---|---|
| 1 | FAIL | L3 | Match Reply to Matter | `…parameters.jsCode` (line 43) | `const received_at = String(j.date \|\| headers.date \|\| new Date().toISOString());` |
| 2 | FAIL | L1 | Validate Reply JSON | `…parameters.jsCode` (line 121) | `communication_id: 'COM-' + new Date().toISOString()…` |
| 3 | FAIL | L2 | Log Inbound | `…parameters.columns.value.idempotency_key` | `={{ $json.matter_id + '\|' + $now.toMillis() }}` |
| 4 | WARN | L5 | Log New Inbound | `…parameters.columns.schema` | `operation=appendOrUpdate sheet=Events maps 11 columns, columns.schema is []` |
| 5 | FAIL | L5 | Log New Inbound | `…parameters.columns.value` | maps columns absent from the live Events header row: `['not_a_real_column']` |
| 6 | FAIL | L5 | Log New Inbound | `…parameters.columns.matchingColumns` | matches on `correlation_id` but `columns.value` never writes it |
| 7 | FAIL | L5 | Log New Inbound | `…parameters.columns.matchingColumns` | matches on `correlation_id`, absent from the live Events header row |
| 8 | REVIEW | L4 | Validate Reply JSON | `…parameters.jsCode` (line 121) | spreads an upstream object and also assigns `communication_id` (other producer: Build Reply Context) |

Corrections emitted, verbatim:

- **L1** — Remove the clock. `communication_id` must be a pure function of the message identity so it is identical on every replay.
- **L2** — Derive `idempotency_key` from immutable ingress data only: `matter_id + '|' + provider_message_id`.
- **L3** — An absent provider timestamp must be empty, not "now". `received_at` feeds the ingress fingerprint, so a clock fallback makes an ordinary retry look like a different message and raises a false `IDEMPOTENCY_CONFLICT`.
- **L4** — Confirm the assignment is not overwriting the upstream deterministic value. If it is, delete it and let the spread carry it.
- **L5** — Populate `columns.schema` with one entry per live column so the node declares its contract instead of resolving headers at runtime. Write the column you match on. A mapped column the sheet lacks is what broke WF9.

Finding 8 is the one worth noting: **L4 independently rediscovered the real defect** — the
node that spread the resolver output and then re-assigned `communication_id` over it, which
made the Telegram notice report an id absent from the sheet. That was found by hand earlier
today; the linter now catches it automatically.

## What L5 actually checks

Beyond "schema is populated": every mapped column exists in the **live** header row, no
cached schema entry names a column the sheet lacks, an `appendOrUpdate` has
`matchingColumns`, and the matched column is one the node actually writes. The live header
sets are hardcoded from direct sheet reads (execs 291 and 311), never from n8n's cached node
schema — reading the cache would reproduce the assumption that broke WF9.

## Running it

```
python3 wf5_structural_lint.py /path/to/wf5.json     # exit 1 on any FAIL
```

It cannot run inside n8n: reading workflow definitions needs an `n8nApi` credential, which
does not exist on this instance — the same blocker that left QA Autopilot's self-repair dead.
Create that credential and this becomes a scheduled workflow linting WF1–WF5 to Telegram.

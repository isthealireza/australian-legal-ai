# WF5 published — snapshot-based L5, both suites green, active definition re-linted

```
1. Linter run with a fresh header snapshot   DONE   exec 318 snapshot, 5/5 PASS
2. Draft unchanged during the sequence       DONE   cdb05a7e throughout
3. 29/29 matching suite                      PASS   exec 319
4. Real-sheet replay round trip              PASS   exec 320, ROUND TRIP PROVEN
5. Published                                 DONE   activeVersionId cdb05a7e
6. Active definition re-fetched and re-linted PASS  5/5, 0 findings
7. dry_run                                   STILL "true"  (verified verbatim)
```

## Your correction was right, and it caught a real vacuous pass

L5 now requires a fresh snapshot: `sheet_id`, `retrieved_at`, per-tab `headers`,
`header_count`, `header_hash`. No snapshot, stale snapshot, snapshot for a different
spreadsheet, or a tab the snapshot does not cover → **REVIEW, never PASS**.

Negative controls, both confirmed:

```
no --headers            -> L5 REVIEW   "cannot validate 18 mapped columns on sheet
                                        'Communications': no --headers snapshot was supplied"
--max-age-minutes 0     -> L5 REVIEW   "snapshot is 1.7 minutes old, older than the
                                        0 minute freshness limit"
```

**Then the stricter check immediately found something the hardcoded version had hidden.**
WF5 also writes to the **Actions** and **Matters** tabs, which my hardcoded header list
never covered. Four write nodes — `Append Next Action`, `Touch Matter (Reply)`,
`Append Follow-up Action`, `Mark Matter Follow-up Due` — were therefore **never
header-validated at all**, and the old linter reported PASS regardless. Exactly the failure
mode you described. Fixed by extending the probe to all four tabs.

## Fresh snapshot (exec 318)

```
sheet_id     : 1L0q0m-h7eqC5CTXDjlCdD8y0NBlErP8s6RJFyFoUknw
retrieved_at : 2026-08-21T11:24:05.742+08:00
source       : QA - Sheet Schema Probe (SEzZkM8OTnQIPpwl) execution 318
Communications : 18 headers, hash H-15e3fc6c
Events         : 10 headers, hash H-5b326a26
Actions        : 18 headers, hash H-8d2e7f57
Matters        : 13 headers, hash H-0f9fa9be
```

All 8 WF5 sheet writers validated against it. `FAIL 0  WARN 0  REVIEW 0`.

## Suites re-confirmed before publishing

- **exec 319** — 29/29, `matching_suite_passes: true`, `replay_suite_passes: true`, no FAIL rows.
- **exec 320** — `ACCEPT` → `ALREADY_RECORDED` → `IDEMPOTENCY_CONFLICT`; fingerprint `ING-a7728903-20` written, stored and read back identically; `content_changed_by_r2/r3: (none)`; comms 2/2/2; matter `R1-STAMP` throughout; all eight t-checks true; `ROUND TRIP PROVEN`.

## Published

`activeVersionId: cdb05a7e-07ce-48b5-99b9-d37192f33d40`. Re-fetched and re-linted with
`--active`: 44 nodes, `published: YES, dump == live`, 5/5 PASS, 0 findings.

## A linter limitation I found while doing step 6, now fixed

A `get_workflow_details` dump can carry **two** node arrays: `workflow.nodes` is the
**draft**, and `workflow.activeVersion.nodes` is the published copy. My linter read
`workflow.nodes` — so on any workflow with an unpublished draft it was linting what is
*staged*, not what is *running*. For WF5 that is now moot (draft == active), but it would
have quietly given the wrong answer elsewhere.

The linter now takes `--active` to select the published copy, and when reading the draft it
warns if the dump also holds a differently-sized published copy.

This also explains the dump shrinking 161,365 → 85,848 bytes after publishing: before, it
carried both copies; now they are the same version.

## Unrelated finding on WF4 that needs your decision

Verifying `dry_run` surfaced this. WF4 has an **unpublished draft**:

```
versionId       ff0dc616-1ca7-4d9f-853e-60fbf874b601   (draft, 74 nodes)
activeVersionId fd328c8b-c2e2-47a6-92bb-59638b0dd002   (live,  72 nodes)
```

The two extra draft nodes are **`QA Manual Start`** (a `manualTrigger`) and
**`QA Router Payload`** (a `set` node). **They are not mine** — I never added a trigger or a
payload node to WF4. So the "72 nodes" in my earlier reports was the published count, and
the draft was already at 74 before this session.

Two consequences:

1. My `event_id` collision fix for WF4 (`Log Draft Failure`, `Log Gate Refusal`) is sitting in that same unpublished draft. Publishing WF4 publishes **both** — my fix and that QA scaffolding together.
2. `QA Manual Start` is a manual trigger on the workflow that sends email. Harmless while `dry_run` is `"true"`, but once published it is a live manual entry point into the draft/approval path. Worth a look before WF4 is ever published or `dry_run` flipped.

I have not touched WF4 in this pass.

## Your closing point stands

Static linting cannot replace post-publish runtime verification, and nothing here claims
otherwise. WF5 is now live with the ingress-only resolver; the first genuine reply is the
runtime test, and until one arrives nothing about production behaviour is observed. What is
observed: the resolver logic (29/29), the real-sheet round trip against the true 18-column
schema, and five structural invariants against the live active definition with a
seven-minute-old header snapshot.

`dry_run` remains `"true"`: `{"id":"c2","name":"dry_run","value":"true","type":"string"}`.
Nothing can leave the account.

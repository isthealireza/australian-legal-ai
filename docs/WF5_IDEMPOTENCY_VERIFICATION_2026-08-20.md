# WF5 idempotency verification — read-only

WF5 was not modified, published or activated in this pass. No fix applied.
Evidence: `QA - Sheet Schema Probe` (`SEzZkM8OTnQIPpwl`) executions **289** and **290**
(reads only, writes nothing), plus a fresh metadata read of WF5.

**All five checks PASS.**

---

## 1. `Communications` contains an `idempotency_key` column — PASS

Read from the **live sheet**, not from n8n's cached node schema. That distinction matters:
cached schema is exactly what broke WF9 ("Column names were updated after the node's
setup … Missing columns"). Execution 289 returned an empty item because Communications has
no data rows, so headers were unreadable; execution 290 re-read it with
`headerRow = firstDataRow = 1` so the header row itself returns as a data row.

`comms_header_count: 17`, and the header names came back both as keys and as values:

```
communication_id, matter_id, action_id, direction, channel, provider_message_id,
thread_id, recipient, subject, summary, classification, received_at, response_due,
next_action, draft_id, approval_id, idempotency_key
```

`idempotency_key_present_in_comms: true`.

Cross-check against every column `Log Inbound` writes:
`log_inbound_columns_missing_from_sheet: []`, `log_inbound_all_columns_exist: true`.
All 17 written columns exist in the sheet, and the sets are identical — no drift.

## 2. `Log Inbound` maps a value to `idempotency_key` — PASS

Node `Log Inbound`, `columns.value.idempotency_key`:

```
={{ $json.matter_id + '|' + $json.provider_message_id }}
```

Both components are guaranteed non-empty on the only path that reaches this node:

- `provider_message_id` derives from `String(j.id || '')` in `Match Reply to Matter`; empty makes `has_event` false and `Reply Matched?` diverts the item before `Log Inbound`.
- `matter_id` starts as `''` in `resolveReply`'s base object and is only populated on an authoritative basis. `Log Inbound` sits behind `Sender Verified? [true]`, i.e. `decision === 'ACCEPT'`, which is returned only after `if (!matterId) return out({ reason: 'No authoritative basis.' });`.

So the key cannot degenerate to `"|"`, `"|<id>"` or `"<matter>|undefined"` on this branch.

## 3. `appendOrUpdate` matches the exact field the node writes — PASS

- `operation: "appendOrUpdate"`
- `columns.matchingColumns: [ "idempotency_key" ]`
- key in `columns.value`: `idempotency_key`
- `id` in `columns.schema`: `idempotency_key`
- header in the live sheet: `idempotency_key`

All five are byte-identical, 15 characters, no case or whitespace variance, no
`idempotencyKey` / `Idempotency_Key` variant anywhere in the node. The field being matched
on is the same field being written, and it exists in the sheet.

## 4. The random `event_id` suffix does not replace inbound idempotency — PASS

The randomness is confined to the two Events-sheet loggers, and neither touches
Communications or supplies an idempotency key:

| Node | operation | sheet | event_id | supplies idempotency_key? |
|---|---|---|---|---|
| `Log Unmatched Reply` | append | Events | `'EVT-' + $now.toFormat('yyyyLLddHHmmss') + '-' + Math.floor(Math.random()*1000)` | no |
| `Log Unverified Sender` | append | Events | same pattern | no |

`idempotency_key` is absent from both nodes' `columns.value` **and** from both nodes'
`columns.schema`, and the live Events header set (10 columns: `event_id, event_type,
severity, matter_id, action_id, workflow, node, message, chat_id, created_at`) has no such
column. Both use `matchingColumns: []`, consistent with `append` — an audit log should
append, not deduplicate.

A scan of `Log Inbound`'s entire serialised parameters for `Math.random`, `$now`, `Date.`,
`new Date`, `$runIndex` and `uuid` returns **zero matches**. The inbound key is purely
derived from two immutable Gmail-event values. The two mechanisms are independent:
`event_id` randomness makes audit rows distinguishable; `idempotency_key` determinism makes
inbound rows collapsible.

## 5. Active workflow and draft identical — PASS

Fresh read of WF5:

```
versionId       : 4101d42f-8492-4bff-8288-cb56138f1cb4
activeVersionId : 4101d42f-8492-4bff-8288-cb56138f1cb4
active          : true
updatedAt       : 2026-08-20T04:14:50.138Z
```

Identical. The published version is the verified one.

**Process note worth keeping.** A subagent reusing a cached fetch reported
`sameAsDraft: false` with `activeVersionId 042f8f2b` — the pre-publish value. I nearly
reported point 5 as FAIL on that. Re-reading directly gave the correct result. Version state
must be read fresh, never from a prior response in the same session.

---

## Two observations that are not failures

**Communications has zero data rows.** Consistent with `dry_run = "true"` — nothing has
ever been sent, so there are no `OUTBOUND` rows and no `INBOUND` rows. Consequences worth
holding in mind:

- The duplicate check has nothing to match against today. It becomes effective from the first accepted reply onward. It is not dormant-and-broken, it is correct-and-unexercised.
- On an empty sheet an `appendOrUpdate` necessarily appends, because there is no row to match. That is the correct first-write behaviour.
- The sender-party check will refuse every inbound reply until a real send creates an `OUTBOUND` row. Fail-closed, and expected while `dry_run` is on.

**`communication_id` is non-deterministic.** `Validate Reply JSON` generates it with
`'COM-' + new Date().toISOString()...`. It is not the matching key, so the row match stays
stable. But it means that if the `decision === 'ACCEPT'` gate were ever bypassed, an
`appendOrUpdate` on a replay would overwrite that cell with a fresh timestamp rather than
leave the row untouched. Today the DUPLICATE decision prevents the branch running at all,
so the two protections are belt and braces rather than overlapping exactly. Not a defect;
worth knowing before anyone relies on the write-level protection alone.

## Still outstanding, unchanged

Configuration and live schema are now verified. **Two actual runs producing one row have
still not been observed.** That needs a controlled replay against a throwaway tab, which
writes to your spreadsheet. Not done, not attempted, awaiting your decision.

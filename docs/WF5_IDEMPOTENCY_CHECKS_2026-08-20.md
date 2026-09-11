# WF5 end-to-end idempotency — five checks

WF5 was not modified, published or activated. Fresh reads only; no cached schema and no
reuse of earlier tool responses.

| # | Check | Result |
|---|---|---|
| 1 | `Log Inbound` maps the stable inbound key into `idempotency_key` | **PASS** |
| 2 | The key is identical on replay | **PASS** |
| 3 | `appendOrUpdate` matches exactly `["idempotency_key"]` | **PASS** |
| 4 | A replay creates no second Communication row or action | **NOT PROVEN** |
| 5 | Active workflow version matches the verified draft | **PASS** |

---

## 1. `Log Inbound` maps the stable inbound key — PASS

Fresh full read of WF5. Node `Log Inbound`, `columns.value.idempotency_key`:

```
={{ $json.matter_id + '|' + $json.provider_message_id }}
```

Both inputs are stable across deliveries of the same message: `matter_id` is resolved by
the policy from register state, `provider_message_id` is the Gmail message id.

Scanned every other mapped column in that node for `$now`, `new Date`, `Date.`,
`Math.random`, `$runIndex`, `$execution`: **NONE**. Every other value is a literal
(`"INBOUND"`, `"GMAIL"`, `""`) or a plain `$json.*` passthrough. So no volatility is
introduced inside the node.

The volatility is upstream and does not touch the key. `Validate Reply JSON` sets:

```js
communication_id: 'COM-' + new Date().toISOString().replace(/[^0-9]/g, '').slice(0, 14),
```

That column differs on every run. It is not the matching key, so it cannot break matching —
but see the note at the end about what it does do.

## 2. The key is identical on replay — PASS

`QA - Inbound Key Stability` (`4pok4hCJGh60NbM2`), execution **292**, status `success`,
**6 of 6 checks pass**. Both key expressions were evaluated by an n8n Set node — the
expression engine's own output for the exact strings mapped in production — not
re-implemented in JavaScript.

Fixture: two deliveries of the same Gmail message, with the Gmail-fixed fields identical
and the write-time fields deliberately different.

| Check | Statement | Result |
|---|---|---|
| K1 | `Log Inbound` key identical across replay | PASS — `MAT-20260801-001\|MSG-IN-1` both times |
| K2 | `Append Next Action` key identical across replay | PASS — `MAT-20260801-001\|MSG-IN-1\|OWNER_DECISION` both times |
| K3 | Key has no `undefined`, `null` or empty segment | PASS |
| K4 | A volatile mapped column DOES differ, so this is a genuine replay and not a copy | PASS — `communication_id` `COM-20260820050856` vs `COM-20260820061142` |
| K5 | The key is unaffected by that volatile column | PASS |
| K6 | The key derives only from the matter and the Gmail message id | PASS |

K4 matters: without it, K1 would be a tautology. The fixture proves the two runs differ in
a mapped column while the key does not.

## 3. `appendOrUpdate` matches exactly `["idempotency_key"]` — PASS

Fresh read of `Log Inbound`:

- `operation`: `"appendOrUpdate"`
- `columns.matchingColumns`: `["idempotency_key"]` — **array length exactly 1**
- key in `columns.value`: `idempotency_key`
- live sheet header (probe exec 291): `idempotency_key` present

One element, not a superset. The matched field is the written field and it exists in the
sheet.

`Log Inbound` is also the **only** node in WF5 that writes to `Communications`. The other
two references are `Load Comms (FU)` and `Load Comms (Reply)`, both reads (no `operation`
key, so the Sheets default). No second writer can create a competing row.

## 4. A replay creates no second Communication row or action — NOT PROVEN

This cannot be established read-only, and I will not report it as passing.

What is established: the `DUPLICATE` decision stops the write branch before `Log Inbound`
(verified logic, exec 288, R1–R4), the key is stable (exec 292), the operation is
`appendOrUpdate` on exactly that key (fresh read), and the column exists in the live sheet
(exec 291). Every precondition for the behaviour holds.

What is not established: **two actual runs producing one row.** Nobody has observed the
Google Sheets API collapse a second write. That requires writing.

There is also a real reason not to assume it. `Communications` currently has **zero data
rows**. `appendOrUpdate` matches against existing rows; with none, the first write appends.
The matching path has therefore never executed even once against this sheet.

The minimal way to close it, in ascending order of intrusiveness:

1. **Throwaway tab.** Duplicate the `Communications` header row into a tab named e.g. `QA_Communications`, point a copy of `Log Inbound` at it, run the same item twice, read the row count. Touches your spreadsheet but not production data.
2. **One controlled live replay** on a test matter after the first real send, then read the Communications row count.

Option 1 needs your say-so because it writes to your spreadsheet. I have not done it.

## 5. Active version matches the verified draft — PASS

Fresh read of WF5 in the same response as the node data above:

```
versionId       : 4101d42f-8492-4bff-8288-cb56138f1cb4
activeVersionId : 4101d42f-8492-4bff-8288-cb56138f1cb4
active          : true
```

Byte-identical. The live version is the one carrying the policy verified in execution 288.

---

## On your deterministic-`event_id` point

Agreed that a random suffix prevents collisions without preventing duplicate events, and
agreed that `idempotency_key` must not be used on `Events` — the live header set has no such
column (probe exec 291), so mapping it would fail the way WF9 failed.

Two constraints worth knowing before that change is specified:

**Deduplicating on `Events` would have to match on `event_id` itself**, since that is the
only candidate column. That means `operation: appendOrUpdate` with
`matchingColumns: ["event_id"]` and `event_id` derived deterministically, e.g.
`'EVT-INBOUND-' + provider_message_id`.

**`Log Unmatched Reply` is the one node where that is not derivable.** It fires precisely
when `has_event` is false — that is, when the Gmail item carried no message id. There is no
stable identifier to hash, so a deterministic `event_id` cannot be built there. Candidates
would be a content hash of subject plus received_at, which is weaker and can collide across
genuinely distinct messages.

`Log Unverified Sender` is different: it fires on the blocked branch where
`provider_message_id` is present, so a deterministic key IS derivable there, and that is
where duplicate-event suppression would actually pay off — a counterparty repeatedly
replying from an unrecognised address currently produces one WARNING row per delivery.

I have not implemented either. Awaiting your decision on which node, which key, and whether
audit rows should collapse at all — an audit log that deduplicates loses the count of how
many times something was attempted, which is sometimes the fact you want.

## Artifacts

| Workflow | ID | Purpose |
|---|---|---|
| QA - WF5 Reply Policy v2 | `BAKIml11QKedtH9d` | policy correctness, exec 288, 17/17 |
| QA - Sheet Schema Probe | `SEzZkM8OTnQIPpwl` | live sheet headers, exec 291 |
| QA - Inbound Key Stability | `4pok4hCJGh60NbM2` | key stability on replay, exec 292, 6/6 |

All three are manual-trigger, read-only, and write nothing to any sheet.

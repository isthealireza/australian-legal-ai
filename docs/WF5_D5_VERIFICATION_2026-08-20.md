# WF5 D5 verification — reply matching

**Verdict: WF5 is not safe. I am not claiming the system is fixed.**
10 cases, **5 PASS / 5 FAIL**. One failure is an unsafe wrong-matter attribution with a
state change. One is a defect I introduced yesterday and did not catch.

Harness: `QA - WF5 Reply Matching Verification` (`VelAeCU71KHELUJP`). Read-only —
no sheet reads, no sheet writes, no Gmail, no Telegram, no model calls. It runs the
**verbatim production `Match Reply to Matter` code** and the **verbatim published
`Build Reply Context` code** against synthetic fixtures whose Code nodes carry the
production node names, so the code under test runs unmodified. No production workflow
was changed in this pass.

Executions: **285** (8 cases), **286** (9 cases), **287** (10 cases, final).

## Your D5 premise, confirmed

`Match Reply to Matter` runs before any sheet load and uses only the Gmail event. That
part is correct. But what it uses from the event is:

```js
const hay = subject + '\n' + body;
const m = hay.match(/\[(MAT-[A-Za-z0-9-]+)\]/i);
```

**There is no thread matching anywhere in WF5.** `threadId` is captured and passed
downstream but never used to resolve a matter. The matcher takes the **first**
`[MAT-…]` occurrence in subject-then-body — so a tag quoted in a forwarded body can
outrank the thread the message actually belongs to.

## Results (execution 287)

| Case | Scenario | Result | Matter matched | Verified | Decided at | State change |
|---|---|---|---|---|---|---|
| C1 | Correct tag in subject | **PASS** | MAT-20260801-001 | yes | Sender Verified? | Log Inbound + Append Next Action + Touch Matter |
| C2 | Correct thread, no tag | **FAIL** | (none) | no | Build Reply Context (unresolved) | Events row only |
| C3 | Wrong tag, not on register | **PASS** | MAT-20260899-999 → rejected | no | Build Reply Context (unresolved) | Events row only |
| C4 | No tag, unknown thread | **PASS** | (none) | no | Build Reply Context (unresolved) | Events row only |
| C5 | Duplicate of C1 | **PASS** | MAT-20260801-001 | yes | Sender Verified? | same keys as C1 |
| C6 | Correct tag, stranger sender | **PASS** | MAT-20260801-001 | no (`SENDER_NOT_A_PARTY`) | Sender Verified? | Events row only |
| C6b | Dry-run-only matter | **FAIL** | MAT-20260802-002 | **yes (wrong)** | Sender Verified? | **Log Inbound + Append Next Action + Touch Matter** |
| C7 | Matter-1 thread, body names matter 2 first | **FAIL** | MAT-20260802-002 | no (`SENDER_NOT_A_PARTY`) | Sender Verified? | Events row only |
| C8 | Shared counterparty, wrong tag, thread present | **FAIL** | MAT-20260803-003 | no (`THREAD_MISMATCH`) | Sender Verified? | Events row only |
| C9 | **Shared counterparty, wrong tag, NO thread id** | **FAIL** | **MAT-20260803-003 (wrong)** | **yes** | Sender Verified? | **Log Inbound + Append Next Action + Touch Matter** |

Requested per-case detail is in `rows` on the `Report` node of execution 287.
`next_action_id` for C9 was `ACT-20260803-003-002`; `log_inbound_key`
`MAT-20260803-003|MSG-IN-10`.

## The one genuinely unsafe failure: C9

An insurer's claims address is a party to two matters. They send a **new** message rather
than a threaded reply (routine for claims systems), and their boilerplate quotes the
**other** matter's tag. Result:

- matter resolved to **MAT-20260803-003** — the wrong matter
- `sender_verified: true` — they genuinely are a party to that matter
- `would_classify: true` — the reply is classified as an OFFER / DEADLINE_NOTICE / etc.
- action created against the wrong legal matter, and `Touch Matter (Reply)` moves that
  matter's status

This is exactly the D5 harm you named. It survives my sender gate because the sender check
asks "is this address a party to the matter the tag named?" and the answer is yes. The
thread check that would have caught it is conditional:

```js
} else if (threads.size && replyThread && !threads.has(replyThread)) {
```

With `replyThread` empty, the check is skipped entirely. C8 proves the check works when a
thread id is present; C9 proves it is bypassed when one is not.

## The defect I introduced: C6b

I claimed dry-run rows do not establish correspondence. The code does exclude them from
`outbound` — and then re-admits the address by a second route:

```js
outbound.forEach(c => { const e = emailOf(c.recipient); if (e) known.add(e); });
actions.filter(a => up(a.matter_id) === up(matter.matter_id))
  .forEach(a => { const e = emailOf(a.recipient); if (e) known.add(e); });
```

The second block adds the **intended** recipient of an action that was never sent. So on a
matter where nothing has left the account, mail from the drafted recipient's address is
accepted as verified correspondence. Since `From` is trivially spoofable without SPF/DKIM
checks — and WF5 does none — this is a real weakening of the gate, not a cosmetic one.
My changelog asserted the dry-run rule held. It does not. That claim was wrong.

## C2 and C7: fail-safe, not safe

Both refuse a legitimate reply. Neither creates state. C7 is instructive: the matcher
picked the wrong matter (MAT-20260802-002, quoted first in the body) and the sender gate
caught it only because that counterparty happened not to be a party to matter 2. Change
the fixture so both matters share a counterparty and you get C8/C9. **C7 passing safely is
luck, not design.**

## Duplicate handling (case 5)

`duplicate_keys_identical: true`. C1 and C5 both derive
`log_inbound_key = MAT-20260801-001|MSG-IN-1` and
`next_action_key = MAT-20260801-001|MSG-IN-1|OWNER_DECISION`.

Both production writes are `appendOrUpdate` matched on those keys, so a redelivered Gmail
message updates one row rather than appending a second. **Caveat on the strength of this
evidence:** I verified *key derivation is stable*, not the Sheets behaviour itself — that
would need writes. Idempotency here is correct by construction, and untested in anger.

## Shadow evaluation of a candidate fix

Computed in the same run, changing nothing. Two changes: resolve by thread first with the
tag as fallback, and build the known-party set from real `OUTBOUND`/`OUTBOUND_PENDING`
correspondence only. Result **8 PASS / 2 FAIL**:

- fixes C2, C6b, C7, C8
- **does not fix C9** — with no thread id there is nothing but the tag to go on
- **breaks C3**: thread-first silently overrode an explicit tag naming a non-existent
  matter, and verified it against the thread's matter

C3 is a real design question I should not decide for you: when an immutable thread id and
a user-editable tag disagree, which wins, and should a disagreement be a refusal rather
than a resolution? My view is that thread should win on attribution, and any *contradiction*
between thread and tag should refuse and notify — but that is a policy call about your
matters, and C3's expectation may be the thing that's wrong, not the logic.

For C9 the only sound answer I can see is: if the matter cannot be resolved by thread, and
the sender is a party to more than one matter, refuse and ask. That trades some friction
for the elimination of silent wrong-matter attribution.

## Your two specific points

**1. `Log Unmatched Reply` event_id — confirmed defective.** Current value, verbatim:

```
={{ 'EVT-' + $now.toFormat('yyyyLLddHHmmss') }}
```

No suffix. `Log Unverified Sender` (added yesterday) has one; this node was missed. And
the collision is not theoretical: the Gmail trigger polls hourly and returns a **batch**,
so several unmatched replies are processed within the same second of the same execution
and will write identical `event_id` values. Not fixed — read-only pass.

**2. `Source Registry` empty-URL path — your reading is right.**

```js
return list.length
  ? list.map(s => ({ json: { url: s.url, want: s.want, cite: s.cite, landing: s.landing } }))
  : [{ json: { url: '', want: [], cite: '', landing: '' } }];
```

Downstream, `Distil Sources` line 108 does `if (!url) return;` — the item is skipped
entirely, so `sources` is `[]`, and `sources_failed: sources.length - retrieved.length`
evaluates to **0**. So the record would read "0 retrieved, 0 failed": a retrieval failure
presented as a clean no-source result, with no audit row and nothing for a linter to see.

Two mitigations, both partial: `research_status` still becomes `UNVERIFIED` (retrieved
length 0), so the approval gate still refuses to send a draft that states law. And the
path is currently **unreachable** — REGISTRY has all four playbook keys plus the
`generic_legal_research_v1` fallback, so `list.length` is never 0. That makes it latent,
not active. It should still emit an explicit failure record rather than an empty URL.

## What I am not claiming

- Not claiming WF5 is safe. Five of ten cases fail and one attributes a reply to the wrong legal matter with a state change.
- Not claiming the dry-run exclusion works. C6b disproves it.
- Not claiming Sheets-level idempotency is exercised. Only key stability is.
- Nothing in production was changed in this pass. The three defects above (C9 resolution, C6b known-party source, `Log Unmatched Reply` event_id) are unfixed and awaiting your authorisation.

# n8n Legal AI — changes applied 2026-08-20

All changes published and live. `dry_run` was **not** touched: it is still `"true"` in
WF4 Config, so the system still cannot send. That switch is yours.

---

## Step 1 — Real WA law. Done.

### The actual root cause

Your diagnosis was right about the symptom and one layer off on the cause. `Build Draft
Context` did not "hand an empty list" because the list was unpopulated — `source_policy`
was populated on all four playbooks. It handed an empty list because of this:

```js
const allowedHosts = new Set();
for (const u of (pb.source_policy || [])) {
  try { allowedHosts.add(new URL(u).host.toLowerCase()); } catch (e) {}
}
const urls = (pb.source_policy || []).filter(u => {
  try { const h = new URL(u); return h.protocol === 'https:' && allowedHosts.has(...); }
  catch (e) { return false; }
}).slice(0, 6);
```

`new URL()` throws in the n8n Code sandbox. Both `try/catch` blocks swallowed it.
`allowedHosts` stayed empty, the filter then rejected every candidate, and `urls` was
structurally `[]` on every run. `Distil Sources` even documents this in its own header
comment — "which is why the url list arrives empty" — but the fix was never carried back
to the node that caused it.

So `sources_retrieved` could never be anything but 0, and every legal sentence came out
`[UNVERIFIED]`. Not a content problem. A swallowed exception.

### The second bug, which would have bitten immediately after

Even with URLs flowing, this line would have defeated the whole exercise:

```js
excerpt: usable ? text.slice(0, 6000) : '',
```

Every one of these documents is an entire consolidated Act. The first 6000 characters are
the table of contents. The model would have received a contents listing and no provision
text, while the record said `RETRIEVED`. That is the fabricated-authority failure mode in
a new costume.

### What I did instead of guessing

Built `QA - Source Retrieval Probe` (`hNw2SnG6NB5KO88z`) — manual trigger, GET only,
writes nothing. It runs the real n8n HTTP node against candidate URLs and applies the
exact verification logic, so URL viability is proven before WF4 changes. Three iterations:

| Probe finding | Consequence |
|---|---|
| `legislation.wa.gov.au` canonical `?OpenAgent&query=mrdoc_NNNNN.htm` fetches full Act text | **usable** |
| `www.fairwork.gov.au` returns **0 bytes** to the n8n node | dropped |
| `www.austlii.edu.au` returns 403 Cloudflare challenge | dropped |
| `www.wa.gov.au` fetches, but carries no provision text — the excerpt was a language-selector menu | dropped |
| `legislation.gov.au` Fair Work Act epub: **every part serves the same table of contents** | dropped |

That last one matters: the research subagent had marked the Fair Work Act body URL as
usable because it saw the section headings — in the TOC. The probe scored it 0 and I
confirmed independently that no operative text is on the page. It never reached the
workflow.

### Anchoring

First-match anchoring hit the contents listing. Last-match anchoring hit whichever later
section happened to reuse the phrase — for the Limitation Act it landed on s 30
(claimants under 15) instead of s 13. Neither is acceptable when the output is a citation.

The fix is a property of the source format: in the stripped body a real heading is
preceded by a section-number marker rendered as digits, space, dot — `55 .Driver in
incident...` — while the contents listing has no space: `55.Driver in incident...`.
Matches are scored on that, plus operative-language proximity, minus a trailing page
number. Body headings score 14. Table-of-contents pages score 0. The threshold is 10.

Probe exec 284, all five WA Acts, anchor landed on the provision:

- **Limitation Act 2005 (WA) s 13** — "13 .General limitation period — 6 years (1)An action on any cause of action cannot be commenced if 6 years have elapsed since the cause of action accrued."
- **Road Traffic Act 1974 (WA) s 55** — "55 .Driver in incident occasioning property damage to stop and give information (1)If a vehicle driven by a person (the driver) is involved in an incident in which any property is damaged, the driver must stop immediately..."
- **Magistrates Court (Civil Proceedings) Act 2004 (WA) s 4** — "4 .Term used: jurisdictional limit In this Part — jurisdictional limit means $50 000 and, on and after 1 January 2009, means $75 000."
- **Motor Vehicle (Third Party Insurance) Act 1943 (WA) s 4** — "4 .Insurance against third party risks (1)When any motor vehicle is on a road there is required to be in force..."
- **Minimum Conditions of Employment Act 1993 (WA) s 9A** — "9A .Maximum hours of work (1)An employee is not to be required or requested by an employer to work more than —"

Note the $75,000 Magistrates Court figure is now **read from the Act**, not asserted.

### Shipped to WF4

- **`Expand Source URLs` → renamed `Source Registry`.** It is now the single place a legal source URL lives, keyed by playbook, each entry carrying the URL, the operative phrases to anchor on, a citation label, and the landing-page URL for future staleness checking. Host parsing is regex, not `new URL()`.
- **`Distil Sources` rewritten** to excerpt the provision instead of the document head, to require a scored body-heading match, and to add a new fail-closed status `PINPOINT_NOT_FOUND` for when a declared provision cannot be located (which is what happens after a reconsolidation renumbers an Act). New counters: `sources_pinpoint_missing`, `sources_cited`.
- **`Fetch Source` timeout 20s → 30s.** The Road Traffic Act is 1.2 MB.
- `Build Draft Context`'s own `urls` field is now dead. I left the playbook blob untouched rather than rewrite 18 KB of legal domain data for no behavioural gain.

Coverage by playbook: motor vehicle gets four Acts; employment and contractor get the WA
state-system floor (MCE Act) plus the Limitation Act; generic gets Limitation and
Magistrates Court. **Commonwealth employment law has no retrievable provision text from
this node.** Anything resting on the Fair Work Act stays `[UNVERIFIED]` and gate check 6.6
refuses to send it. That is the honest state and I did not paper over it.

---

## Step 3 — Inbound trust. Done.

You were right and it was worse than "a stranger who guesses a subject line". The
`[MAT-...]` tag travels in every letter the system sends, so it appears in any forward of
one. The tag identifies a matter; it never authenticated a sender.

`Build Reply Context` now loads Communications and requires, before the classifier sees
anything:

1. the sender address to be one this matter has actually written to (from `OUTBOUND` /
   `OUTBOUND_PENDING` rows, plus recipients on the matter's actions), and
2. the mail thread to be one we sent, where thread ids exist.

Dry-run rows deliberately do **not** establish correspondence — nothing was sent, so
nothing can be a reply to it.

Failures route to a new `Sender Verified?` gate → `Log Unverified Sender`
(`INBOUND_REPLY_SENDER_UNVERIFIED`, WARNING) → Telegram notice. No action created, no
classification, no state change. Four failure kinds are distinguished: `NO_SENDER`,
`NO_CORRESPONDENCE`, `SENDER_NOT_A_PARTY`, `THREAD_MISMATCH`.

**Known trade-off, your call:** a genuine counterparty replying from a different address
(the classic `claims@insurer` vs a named adjuster) will be refused. The refusal is
visible, explains itself, and tells you to add the address as the recipient on the matter.
I chose fail-closed with a loud notice over a heuristic. If that proves annoying in
practice, the fix is an allowlist column on Matters, not a loosening of this gate.

---

## Step 4 — Small holes. Partly done.

Done:

- **`answerCallbackQuery`** added to WF1 as a terminal side branch off the owner check, so the routing path is untouched. Buttons stop spinning.
- **Public QA webhook deactivated.** `QA - WF9 Error Handler Test` was active with an unauthenticated public GET whose only job is to throw — anyone with the URL could spam your Telegram and the Events sheet. WF9 is verified; it did not need to stay armed.
- **Retries on all ten WF5 sheet reads** (digest, follow-up, reply). Exec 279 died at `Load Matters (Digest)` on "Service unavailable" and you got no digest that morning. Three tries, two seconds apart, matching WF9.
- **`event_id` collisions** fixed in WF2 `Log Plan Failure` and WF4 `Log Draft Failure` / `Log Gate Refusal` — they now carry the random suffix WF1 always had.

Not done, because they need the spreadsheet, not the workflow:

- `idempotency_key` column on Evidence
- `is_test` column on Matters (the gate currently infers test data from the title via `suspectData()`)
- status history on Matters

Add those three columns and I'll wire them.

---

## Steps 2, 5, 6 — deliberately left

**Step 2, one real send.** Yours to trigger, and I agree with the choice of a
preserve-footage request as the first one. Before flipping `dry_run`, do a dry-run draft
on a real motor-vehicle matter: it will now write real `Sources` rows and you can read
`verification_status` and `pinpoints` on the sheet and see the cited provision in the
approval message. That is the end-to-end proof of Step 1 without sending anything. I did
not run it myself because it writes register rows against a matter I have not inspected.

**Step 5, untested paths.** Still untested. The probe workflow is the pattern to reuse:
isolate the logic, run it against reality, read the classification. Worth doing for the
vision branch and gate checks 6.5–6.7 before the first send, not after.

**Step 6, the QA linter.** `QA - Source Retrieval Probe` is the seed — it already is a
source linter, it just needs a schedule and a Telegram report. The `landing` URL on every
registry entry is there so the linter can re-resolve a drifted `mrdoc` id. Note the real
staleness risk: those ids change on reconsolidation, and a dead id fails closed rather
than citing the wrong thing.

---

## Files and versions

| Workflow | ID | Published version |
|---|---|---|
| 1 - Telegram Intake and Command Router | `xUcAXTgocHPsHy5Y` | `ca5c3a76` |
| 2 - Matter Classification and Planning | `OaVCEsrt2qpo28rB` | `c5afd2f6` |
| 4 - Research Drafting Approval and Dispatch | `zKr24IThF30e6jXw` | `fd328c8b` |
| 5 - Inbound Replies and Daily Supervisor | `zDLoMgW42jUm25Q4` | `042f8f2b` |
| QA - Source Retrieval Probe | `hNw2SnG6NB5KO88z` | new, manual only |
| QA - WF9 Error Handler Test | `aSygXnnfLDXRR3fK` | deactivated |

Every edit went in as a new version with a description, so n8n's version history has the
rationale and rollback is one click per workflow.

One process note worth keeping: `update_workflow` writes a **draft**. All four workflows
sat unpublished until I explicitly published them — WF4's live version was still running
the old `c.urls` node after the fix was "applied". Worth checking `sameAsDraft` before
believing a change is live.

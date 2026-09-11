# Demo Runsheet — Grounded WA Legislation Research Assistant

**Date:** 2026-09-09
**Branch:** `test/scenario-suite` @ `1042de9` (known-good)
**Answer model:** `mock` (deterministic; no live provider, no network, no cost)

Every query and command below was run against the local server and the
behaviour described is what actually happened. Nothing is written from
expectation.

---

## 1. Start it (two commands, PowerShell)

```powershell
$env:LEGAL_AI_WA_CORPUS_ROOT = "tests/fixtures/wa_legislation"; $env:LEGAL_AI_PROVISION_ROOT = "tests/fixtures/wa_legislation"; $env:LEGAL_AI_ANSWER_PROVIDER = "mock"
```

```powershell
uv run uvicorn legal_ai.api.main:create_app --factory --port 8099
```

Open **http://127.0.0.1:8099/** — the single-page interface loads the indexed
corpus, shows the permanent non-lawyer disclaimer, and the status pill reads
"Ready · mock model".

> The three `$env:` assignments are command one (setup); `uv run uvicorn …` is
> command two (start). Both run from the repository root.

## 2. Live queries

The browser interface offers only what is indexed, as clickable "situations"
(with the citation shown underneath). You cannot type an arbitrary Act or
jurisdiction into the UI — by design, so an out-of-corpus or cross-jurisdiction
question can never even be formed from the list. The two successes below are
run through the UI; the two refusals are run against the same `/api/research`
endpoint from a terminal, because the UI correctly offers no way to ask them.

### Query 1 — succeeds with a real citation (through the UI)
**In the sidebar, click "Traffic incident involving property damage"** (Road
Traffic Act 1974 · s 55), then type this in the Ask box and submit:

```
A driver hit a parked car and damaged it. What does the law require the driver to do?
```

**Audience sees:** `ANSWERED` — a proposition naming *section 55 of the Road
Traffic Act 1974*, with a full citation: source id, `14-t0-00` version,
compilation date 2025-01-10, the official legislation.wa.gov.au URL, the
SHA-256 digest of the recorded bytes, and the verbatim opening line of the
provision as the quote.

**Say while it runs:** "The system only answers from the exact recorded source —
here it finds the stop-and-give-information duty and proves the citation points
at the byte-exact PDF it ingested."

### Query 2 — succeeds with a real citation (through the UI)
**Click "Implied conditions as to quality or fitness"** (Sale of Goods Act
1895 · s 14), then type and submit:

```
I bought a second-hand fridge that doesn't cool properly. Is there an implied condition about quality?
```

**Audience sees:** `ANSWERED` — *section 14 of the Sale of Goods Act 1895*,
with the same full citation chain (digest, official URL, quote).

**Say while it runs:** "A real consumer question about a 130-year-old Act — it
answers only because the provision is actually in the indexed corpus, and it
recomputes the digest over the exact recorded bytes before citing anything."

### Query 3 — refuses: an Act we have not recorded (terminal, API)
**Paste into a second PowerShell window:**

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8099/api/research" -ContentType "application/json" -Body '{"question":"What are my consumer guarantees under the Australian Consumer Law?","jurisdiction":"Commonwealth","act_title":"Competition and Consumer Act 2010","provision_identifier":"s 54","pinpoint":"section 54"}'
```

**Audience sees:** `outcome=REFUSED`, `code=RESEARCH_REFUSED`, and the permanent
disclaimer. No answer, no citation, no proposition.

**Say while it runs:** "The Australian Consumer Law is the Competition and
Consumer Act 2010 (Commonwealth) — we have not indexed it, so the system
refuses instead of guessing from a Western Australian Act that happens to
mention it."

### Query 4 — refuses: wrong-jurisdiction evidence (terminal, API)
**Paste into the same second PowerShell window:**

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8099/api/research" -ContentType "application/json" -Body '{"question":"A driver damaged my car in Sydney. What must they do?","jurisdiction":"NSW","act_title":"Road Traffic Act 1974","provision_identifier":"s 55","pinpoint":"section 55"}'
```

**Audience sees:** `outcome=REFUSED`, `code=RESEARCH_REFUSED`.

**Say while it runs:** "This is a NSW problem against a WA-only corpus. A
cross-jurisdiction answer is a release-blocking defect, so the system refuses
rather than answer out of a WA Act."

---

## 3. Do NOT demo

- **Contract review.** There is no contract analysis, clause extraction, or
  document drafting. This boundary is documented (`MVP_ROADMAP.md` §11 "Not
  now") but is **not yet enforced by a dedicated scope check in code** — a
  request phrased as "review this contract" would only be refused if it cannot
  be grounded in the indexed corpus, not because the system recognises the
  request kind. Do not invite the audience to try it, and do not claim the
  system refuses it "by name".
- **Live retrieval.** The demo reads recorded, version-controlled fixtures
  only. There is no runtime network path. Do not imply it looks up current law.
- **Any live language model.** The answer adapter is `mock`, which restates the
  retrieved provision's identity and quotes it verbatim. It does not paraphrase,
  reason, or summarise. Do not imply an LLM is answering.
- **Entailment verification (level 3).** `entailment_verified` is `false` in the
  demo (mock model + no verifier). Do not claim the statement was independently
  entailed by a second model.
- **"Not legal advice"** must stay on screen; do not dismiss or minimise it.
- **Batch-2 Acts.** The demo runs from `test/scenario-suite`; the eight newer
  Acts from `feat/corpus-batch-2` are not in this corpus. Do not ask about them.

## 4. If asked "can it review a contract?"

Answer honestly:

> "No. Contract review is deliberately out of scope — it is listed under 'Not
> now' in our roadmap. Our own adversarial tests, written yesterday, flagged
> that this boundary is documented but not yet enforced in code: the system
> will only refuse a contract-review request when it happens to fall outside the
> indexed corpus, not because it recognises the request kind. Making that
> boundary a real, enforced refusal is our next task."

That framing turns the gap into evidence of the project's own testing
discipline rather than a hidden defect.
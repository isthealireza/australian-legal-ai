# WA Source Ingestion Runbook

How an operator stages, extracts, verifies and promotes one official Western
Australian source. Written for the owner-approved **C1 batch**: Road Traffic
(Vehicles) Act 2012, version `01-j0-00`.

Nothing in this pipeline downloads anything. Step 1 is a human act, on purpose:
no code in this repository can fetch legislation.

---

## Before you start

Two gates from [ADR 0017](../adr/0017-wa-corpus-expansion-invariants.md) are
yours and cannot be satisfied by running commands:

- **G1** — you accept a specific capture as authoritative.
- **G2** — a person compares each extracted section against the official
  document before its `verified` flag may become `true`.

`promote` refuses without evidence of G1, and refuses any `verified: true`
section without a G2 record naming who checked it and against what.

### A tool mismatch you will hit on this workstation

ADR 0014 §6 recorded the existing ss 55–56 text with `pdftotext` from
**poppler-utils**. The `pdftotext` on this machine is **Xpdf 4.06**. The two lay
text out differently, so the same PDF yields different text and therefore
different digests.

`extract` refuses an unexpected implementation by default. Either install
poppler-utils, or pass `--expect-tool xpdf` to accept the divergence knowingly.
Whichever you choose is recorded in the sections file.

---

## 1. Capture, by hand

Open the official page and download the current consolidated PDF:

`https://www.legislation.wa.gov.au/legislation/statutes.nsf/main_mrtitle_12926_homepage.html`

Note the version suffix, currency start date and the exact URL you used. Record
the UTC moment you downloaded it.

## 2. Write the identity file

The metadata you verified page-side, as JSON. Nothing here is inferred, and the
tooling will refuse a URL the runtime allowlist would later reject.

```json
{
  "act_title": "Road Traffic (Vehicles) Act 2012",
  "act_number": "007 of 2012",
  "assent_date": "2012-05-21",
  "version_suffix": "01-j0-00",
  "currency_start": "2024-10-07",
  "currency_end": "current",
  "status_currency": "Current",
  "status_in_force": true,
  "status_date": "2025-01-10",
  "official_source_url": "https://www.legislation.wa.gov.au/legislation/statutes.nsf/main_mrtitle_12926_homepage.html",
  "retrieved_at_utc": "2026-09-10T00:00:00Z"
}
```

Set `status_date` and `retrieved_at_utc` to what is true at capture time. The
tooling refuses a status date later than the retrieval instant, a currency start
later than the status date, and an assent date later than the currency start.

## 3. Stage

```bash
uv run --locked python -m scripts.wa_ingest.cli --identity identity.json stage --pdf ~/Downloads/rtv2012.pdf
```

Copies the file into `corpus/staging/<slug>/<version>/` and writes a manifest
whose digest and byte length are recomputed from the staged bytes. The active
corpus is untouched.

## 4. Declare the provisions

Edit the staged manifest's `provisions` array by hand, from the official
document. Each entry needs `identifier`, `pinpoint`, and optionally `heading`.

Promotion refuses an empty list, and refuses any two provisions whose
identifiers or pinpoints collide after normalisation — including the cross-field
case where one provision's pinpoint equals another's identifier.

## 5. Extract

Write the page ranges, one entry per provision:

```json
[{"identifier": "s 12", "heading": "…", "first_page": 34, "last_page": 36}]
```

```bash
uv run --locked python -m scripts.wa_ingest.cli --identity identity.json extract --ranges ranges.json
```

Every section is written `verified: false`. The builder has no parameter that
could say otherwise.

## 6. Human verification — gate G2

Read each extracted section against the official document. For each one you
confirm, set `verified` to `true` **and** add a record:

```json
"verification_records": {
  "s 12": {
    "verified_by": "Your Name",
    "verified_against": "official consolidated PDF 01-j0-00, pp 34-36",
    "verified_on": "2026-09-10"
  }
}
```

A `true` flag without a complete record refuses. Leaving everything `false` is
valid and promotes fine — the sections simply stay unusable as drafting
evidence, which is the correct default.

## 7. Owner approval — gate G1

Write `OWNER_APPROVAL.json` beside the staged files. Every field must match the
manifest exactly; approving one capture must not silently approve another.

```json
{
  "approved_by": "owner@example",
  "source_id": "wa_legislation:road_traffic_vehicles_act_2012:consolidated:01-j0-00",
  "official_source_url": "…exactly as in the manifest…",
  "version_suffix": "01-j0-00",
  "currency_start": "2024-10-07",
  "retrieved_at_utc": "…exactly as in the manifest…",
  "sha256": "…exactly as in the manifest…"
}
```

## 8. Check, then promote

```bash
uv run --locked python -m scripts.wa_ingest.cli --identity identity.json check
```

`check` reports the first refusal and writes nothing. When it says ready:

```bash
uv run --locked python -m scripts.wa_ingest.cli --identity identity.json promote
```

The approval record is deliberately **not** copied into the corpus — it is
staging evidence, not corpus content.

## 9. After promotion

Run the full gates and confirm ss 55–56 have not moved:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "not integration"
```

The E1 golden harness is the tripwire. If any ss 55–56 assertion fails, revert
the promotion rather than adjusting the harness.

---

## Refusals you may see

| Refusal | Meaning |
|---|---|
| `STAGING_INCOMPLETE` | a staged file is missing |
| `MANIFEST_DIGEST_MISMATCH` | the staged bytes changed after staging |
| `PROVISIONS_EMPTY` | step 4 was not done |
| `PROVISION_IDENTIFIER_AMBIGUOUS` | two provisions collide after normalisation |
| `SECTIONS_SOURCE_MISMATCH` | the sections file names another source or document |
| `SECTION_TEXT_HASH_MISMATCH` | section text and its digest disagree |
| `SECTION_NOT_IN_MANIFEST` | a section the manifest never declared |
| `SECTION_IDENTIFIER_AMBIGUOUS` | duplicate section identifiers |
| `SECTION_VERIFIED_WITHOUT_RECORD` | gate G2: a `true` flag with no record |
| `EXTRACTION_TOOL_UNRECORDED` | the sections file does not say what produced it |
| `OWNER_APPROVAL_MISSING` / `_MISMATCH` | gate G1 |
| `ACT_TITLE_ALREADY_PRESENT` | ADR 0017 I7: one manifest per Act title |
| `TARGET_ALREADY_EXISTS` | the destination directory is already there |

Every refusal leaves the active corpus exactly as it was.

## Rollback

Before promotion: delete the staging directory. Nothing else was touched.

After promotion: `git checkout -- tests/fixtures/wa_legislation` and remove the
new directory, or revert the commit. No migration runs and no state persists.

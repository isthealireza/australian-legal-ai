# Task A Scope Card — WA Corpus Expansion (three Acts) + scripted ingestion

**Branch:** `feat/corpus-expansion-wa-slice`
**Base:** `84e4ddc` (committed baseline; commits `c068500`, `84e4ddc` untouched)
**Governing decisions:** [ADR 0013](../adr/0013-phase-4-research-evidence-packets.md) (accepted), [ADR 0014](../adr/0014-phase-5-grounded-answering-and-read-only-api.md), [ADR 0015](../adr/0015-derived-provision-text-live-provider-and-entailment.md) (proposed)
**Authority level:** L0 — deterministic, read-only. Official-source PDF acquisition only.
**Owner approval:** candidate list + provisional slices approved 2026-09-08; `scripts/ingest_wa_act.py` approved as part of this card.

## Goal

Expand the WA recorded corpus with three official, in-force statutes so the
demo can answer from more official legislation, with citations, or refuse. Make
act N+1 a single command, not a manual sequence.

## Approved candidate acts and provisional slices

Sections are **candidates** until the PDF text layer confirms them. Record only
sections that exist. Drop and report anything that does not. Never widen a
slice to fill a gap.

| # | Act (registry title) | Version suffix | Currency start | Act no / assent | Official page | Provisional slice (verify) |
|---|---|---|---|---|---|---|
| 1 | Building and Construction Industry (Security of Payment) Act 2021 | `00-e0-00` | 2024-02-01 | 004 of 2021 / 2021-06-25 | `law_a147300.html` | s 8–12 family: right to progress payment, amount, payment claims, schedules |
| 2 | Motor Vehicle Dealers Act 1973 | `06-k0-01` | 2022-07-01 | 101 of 1973 / 1973-12-28 | `law_a525.html` | s 3–7 family: interpretation, licensing obligations/offences |
| 3 | Owner-Drivers (Contracts and Disputes) Act 2007 | `01-g0-00` | 2025-01-31 | 007 of 2007 / 2007-06-06 | `law_a146614.html` | s 4–7 family: interpretation, application, contract requirements/payments |

PDF byte sizes announced by live HEAD checks: 767,632 ; 607,971 ; 505,314.
Only official hosts `legislation.wa.gov.au` and `www.legislation.wa.gov.au` are
authority. No other host is used.

## Deliverables

| Path | Purpose |
|---|---|
| `scripts/ingest_wa_act.py` | Single-command operator ingestion for a new WA Act. Writes only under the injected fixture root. Verifies the PDF text layer. Records only confirmed sections; drops and reports missing ones. Refuses on digest mismatch. No other network call. |
| `tests/scripts/test_ingest_wa_act.py` | Offline tests for the script: manifest authoring, digest-mismatch refusal, correction, no live network. |
| `tests/fixtures/wa_legislation/{slug}/` ×3 | Byte-exact official PDFs, manifest.json (real sha256, content_length, http_status, retrieved_at_utc, official_source_url, version, currency), `provisions/*.txt` + `*.provision.json`, README. |
| `tests/research/test_recorded_wacorpus_slice.py` (+ digest file) | Positive packet tests, byte-integrity tests, digest tests mirroring `test_recorded_fixture_sog_rta.py` / `test_recorded_provision_digests.py`. |
| `docs/execution/CORPUS_EXPANSION_WA_SLICE_SCOPE_CARD.md` | This card. |
| ADR stub note | Commonwealth / `legislation.gov.au` finding recorded **in this scope card only** — no new ADR file. |

## Out of scope

- Commonwealth / `legislation.gov.au` ingestion — deferred, not started (see note below).
- Retrieval changes, vector, authentication, deployment, `.env`, UI, `.local/`.
- Any modification to `PROJECT_GOVERNANCE.md`, `ENGINEERING_WORKFLOW.md`, `LEGAL_AI_MASTER_BLUEPRINT.md`, `MVP_ROADMAP.md`, any existing ADR.
- Any file outside the deliverable paths above (including `src/legal_ai/answering/`, `api/`, `playbooks/` — untouched).
- B2/B3/B5 structure moves (recorded in Task B card).

## Maps to governance

- No grounding, no finding: every provision derives from the verified official PDF bytes; provenance chain enforced (`parent_sha256 == manifest sha256`).
- Fail closed: refusal on digest mismatch, absent provision, missing text layer.
- Never fabricate a section, hash, URL, currency date, or citation. `MISSING` is reported.
- Deterministic code only; text is data, never instruction.

## Commonwealth finding — ADR stub (no new file)

The committed `tests/fixtures/frl/*` recordings are Federal Register **API
captures** consumed only by `sources/frl` contract tests. The proven answering
path is WA-only (`RecordedWaCorpus` → manifest → derive → answering). Plugging
Commonwealth sources into the answering pipeline requires a new corpus
contract, a new evidence-packet type, and a new host-allowlist decision. A
future ADR should record: (1) the FRL document API → immutable capture
boundary; (2) whether `RecordedWaCorpus` becomes source-generic or a new
`CommonwealthCorpus` is built; (3) WB_status/packet contract changes. Recorded
here; do not implement.

## Acceptance criteria

1. `scripts/ingest_wa_act.py <spec>` ingests one Act end-to-end (download,
   digest, manifest, derived provisions, README) in one command. — for all three
   Acts.
2. Every provision's `parent_sha256` equals its manifest `sha256`.
3. Positive: packet + byte-integrity + digest tests pass for all three Acts.
4. Out-of-corpus negative tests remain genuinely out of corpus.
5. A digest-mismatch / missing-text-layer case in the ingest path refuses and
   writes nothing.
6. All repository gates pass; review gate PASS.
7. Repository rules respected; both existing commits untouched.

## Validation (run; real results recorded after remediation)

```
uv run ruff check .           # All checks passed (0 errors)
uv run ruff format --check . # 173 files already formatted (0 would reformat)
uv run mypy .                # Success: no issues found in 173 source files
uv run pytest -m "not integration" -q    # 1082 passed, 47 skipped, 100 deselected
```

The test suite includes these named additions (from verbose run):

- `tests/scripts/test_ingest_wa_act.py` — 16 tests: happy path parametrized over
  all four recorded PDFs; `--expected-sha256` missing; digest mismatch; redirect
  to non-allowlisted host; atomicity (no dir, no `*.tmp` after refusal);
  wrong-host http/https; missing text layer; existing dir; all/partial section
  missing; malformed identifier.
- `tests/research/test_recorded_fixture_corpus_slice.py` — 39 tests:
  validated packet per pinned provision (11), unmodified bytes (3), exact
  single-title selection (3), derivation digest chain (11, incl. parent==packet
  sha256), and derived-text-units-are-substrings-of-source-document (11).
- `tests/scripts/` collects `11` new tests after this task (the full test count
  rises from 1076 to 1082).

Review gate invocations:
```
scripts/deepseek_review.py --dry-run --json   (done; bundle inspected)
scripts/deepseek_review.py (live)             (done; verdict recorded in scope card)
```

## Binary PDF fixtures and the review gate

`scripts/deepseek_review.py` refuses to transmit binary files, so the three
recorded PDFs are never part of a review bundle. Their integrity is proven
instead by two independent mechanisms, both in the bundle:

- the digest chain tests recompute the SHA-256 from the committed stored bytes
  and assert it equals the manifest digest for every Act and provision; and
- [CORPUS_EXPANSION_WA_SLICE_DIGESTS.md](CORPUS_EXPANSION_WA_SLICE_DIGESTS.md)
  records that each PDF was downloaded a second time, fresh, from the official
  host into a temporary directory outside the repository on 2026-09-08, and
  that the re-download SHA-256 matched the committed manifest byte-for-byte.

The two pre-existing modules the ingestion script imports are snapshotted
verbatim for review in
[CORPUS_EXPANSION_WA_SLICE_DEPENDENCIES.md](CORPUS_EXPANSION_WA_SLICE_DEPENDENCIES.md).

## Rollback

Delete the three fixture dirs under `tests/fixtures/wa_legislation/`, delete
`scripts/ingest_wa_act.py` and its tests, revert the test additions and this
card. No migration, no schema, no persistence.
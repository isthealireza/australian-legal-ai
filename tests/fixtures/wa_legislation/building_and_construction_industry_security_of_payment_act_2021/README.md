# WA Legislation Fixture - Building and Construction Industry (Security of Payment) Act 2021 (WA)

Recorded, durable, version-controlled test/evaluation fixture for the
Phase 4/5 research corpus.

## What this is

- One shared **whole-Act official consolidated PDF** of the Building and Construction Industry (Security of Payment) Act 2021
  (WA), captured byte-exact from `legislation.wa.gov.au`.
- A paired manifest recording provenance, version/currency, status, retrieval
  timestamp, SHA-256, and the pinned provisions.
- Per-section text under `provisions/`, derived by
  `scripts/ingest_wa_act.py` from the recorded PDF.

## Files

| File | Purpose |
|---|---|
| `building_and_construction_industry_security_of_payment_act_2021_consolidated_00-e0-00.pdf` | Official consolidated PDF, byte-exact |
| `building_and_construction_industry_security_of_payment_act_2021_consolidated_00-e0-00.manifest.json` | Provenance + SHA-256 + pinpoints |
| `provisions/s_17[.txt\|.provision.json]`, `provisions/s_18[.txt\|.provision.json]`, `provisions/s_22[.txt\|.provision.json]`, `provisions/s_25[.txt\|.provision.json]` | Derived section text + digests |

## Source and version

- **Act:** Building and Construction Industry (Security of Payment) Act 2021 (WA), Act No. 004 of 2021, assent 25 Jun 2021.
- **Version:** Official consolidated version, suffix `00-e0-00`, document
  `mrdoc_46833`.
- **Currency:** start **01 Feb 2024**; end **Current** (in force
  at retrieval).
- **Retrieved (UTC):** `2026-09-08T03:55:31Z`
- **SHA-256:** `9d78bc1fc594d61af5ec095c03d18b7c266aeb8fe52fd776611dee57574edd5b`

## Pinned provisions

- **s 17** - "Right to progress payments"
- **s 18** - "Amount of progress payment"
- **s 22** - "Making payment claims"
- **s 25** - "Response to payment claim: payment schedule"

## Limitations

- **Not a live legal-currency service.** This is a point-in-time snapshot for
  deterministic testing only and may not reflect amendments made after the
  retrieval timestamp.
- The recorded official URLs use host `www.legislation.wa.gov.au`, which is on
  the closed two-host allowlist of exactly `legislation.wa.gov.au` and
  `www.legislation.wa.gov.au` (HTTPS).

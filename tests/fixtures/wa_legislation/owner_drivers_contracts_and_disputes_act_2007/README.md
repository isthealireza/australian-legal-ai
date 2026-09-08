# WA Legislation Fixture - Owner-Drivers (Contracts and Disputes) Act 2007 (WA)

Recorded, durable, version-controlled test/evaluation fixture for the
Phase 4/5 research corpus.

## What this is

- One shared **whole-Act official consolidated PDF** of the Owner-Drivers (Contracts and Disputes) Act 2007
  (WA), captured byte-exact from `legislation.wa.gov.au`.
- A paired manifest recording provenance, version/currency, status, retrieval
  timestamp, SHA-256, and the pinned provisions.
- Per-section text under `provisions/`, derived by
  `scripts/ingest_wa_act.py` from the recorded PDF.

## Files

| File | Purpose |
|---|---|
| `owner_drivers_contracts_and_disputes_act_2007_consolidated_01-g0-00.pdf` | Official consolidated PDF, byte-exact |
| `owner_drivers_contracts_and_disputes_act_2007_consolidated_01-g0-00.manifest.json` | Provenance + SHA-256 + pinpoints |
| `provisions/s_4[.txt\|.provision.json]`, `provisions/s_6[.txt\|.provision.json]`, `provisions/s_7[.txt\|.provision.json]` | Derived section text + digests |

## Source and version

- **Act:** Owner-Drivers (Contracts and Disputes) Act 2007 (WA), Act No. 007 of 2007, assent 06 Jun 2007.
- **Version:** Official consolidated version, suffix `01-g0-00`, document
  `mrdoc_48249`.
- **Currency:** start **31 Jan 2025**; end **Current** (in force
  at retrieval).
- **Retrieved (UTC):** `2026-09-08T03:56:15Z`
- **SHA-256:** `03071c9fe15dfdc3a8c26ebfd9027f5ff6044f91c83e0455ace5b5ac40b43bad`

## Pinned provisions

- **s 4** - "Term used: owner-driver"
- **s 6** - "Application of Act"
- **s 7** - "Act prevails over owner-driver contracts"

## Limitations

- **Not a live legal-currency service.** This is a point-in-time snapshot for
  deterministic testing only and may not reflect amendments made after the
  retrieval timestamp.
- The recorded official URLs use host `www.legislation.wa.gov.au`, which is on
  the closed two-host allowlist of exactly `legislation.wa.gov.au` and
  `www.legislation.wa.gov.au` (HTTPS).

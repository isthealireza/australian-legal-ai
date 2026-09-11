# WA Legislation Fixture - Motor Vehicle Dealers Act 1973 (WA)

Recorded, durable, version-controlled test/evaluation fixture for the
Phase 4/5 research corpus.

## What this is

- One shared **whole-Act official consolidated PDF** of the Motor Vehicle Dealers Act 1973
  (WA), captured byte-exact from `legislation.wa.gov.au`.
- A paired manifest recording provenance, version/currency, status, retrieval
  timestamp, SHA-256, and the pinned provisions.
- Per-section text under `provisions/`, derived by
  `scripts/ingest_wa_act.py` from the recorded PDF.

## Files

| File | Purpose |
|---|---|
| `motor_vehicle_dealers_act_1973_consolidated_06-k0-01.pdf` | Official consolidated PDF, byte-exact |
| `motor_vehicle_dealers_act_1973_consolidated_06-k0-01.manifest.json` | Provenance + SHA-256 + pinpoints |
| `provisions/s_5[.txt\|.provision.json]`, `provisions/s_5A[.txt\|.provision.json]`, `provisions/s_15[.txt\|.provision.json]`, `provisions/s_30[.txt\|.provision.json]` | Derived section text + digests |

## Source and version

- **Act:** Motor Vehicle Dealers Act 1973 (WA), Act No. 101 of 1973, assent 28 Dec 1973.
- **Version:** Official consolidated version, suffix `06-k0-01`, document
  `mrdoc_45172`.
- **Currency:** start **01 Jul 2022**; end **Current** (in force
  at retrieval).
- **Retrieved (UTC):** `2026-09-08T04:18:48Z`
- **SHA-256:** `d91d26a14da9be42c0c477c4ae15a8e9171d11ae68ea5fc77889042a2a1e9990`

## Pinned provisions

- **s 5** - "Terms used"
- **s 5A** - "Classes of business and categories of licence"
- **s 15** - "Vehicle dealer’s licence, application for and grant of"
- **s 30** - "Unlicensed dealing etc., offences as to"

## Limitations

- **Not a live legal-currency service.** This is a point-in-time snapshot for
  deterministic testing only and may not reflect amendments made after the
  retrieval timestamp.
- The recorded official URLs use host `www.legislation.wa.gov.au`, which is on
  the closed two-host allowlist of exactly `legislation.wa.gov.au` and
  `www.legislation.wa.gov.au` (HTTPS).

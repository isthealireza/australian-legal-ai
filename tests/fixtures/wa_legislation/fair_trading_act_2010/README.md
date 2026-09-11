# WA Legislation Fixture - Fair Trading Act 2010 (WA)

Recorded, durable, version-controlled test/evaluation fixture for the
Phase 4/5 research corpus.

## What this is

- One shared **whole-Act official consolidated PDF** of the Fair Trading
  Act 2010 (WA), captured byte-exact from `legislation.wa.gov.au`.
- A paired manifest recording provenance, version/currency, status, retrieval
  timestamp, SHA-256, and the pinned provisions.
- Per-section text under `provisions/`, derived by
  `scripts/derive_wa_provisions.py` from the recorded PDF.

## Files

| File | Purpose |
|---|---|
| `fair_trading_act_2010_consolidated_02-m0-00.pdf` | Official consolidated PDF, byte-exact |
| `fair_trading_act_2010_consolidated_02-m0-00.manifest.json` | Provenance + SHA-256 + pinpoints |
| `provisions/s_18[.txt\|.provision.json]`, `s_19` | Derived section text + digests |

## Source and version

- **Act:** Fair Trading Act 2010 (WA), Act No. 057 of 2010, assent 8 Dec 2010.
- **Version:** Official consolidated version, suffix `02-m0-00`, document
  `mrdoc_48910`.
- **Currency:** start **25 Sep 2025**; end **Current** (in force at retrieval).
- **Retrieved (UTC):** `2026-09-08T02:16:40Z`
- **SHA-256:** `8f4760052a16f26218e506e9c78bbd15bcbf512dbc17d37e4e9bd8e148c1e8eb`

## Pinned provisions

- **s 18** - "Australian Consumer Law text"
- **s 19** - "Application of Australian Consumer Law text" (gives the ACL,
  being Schedule 2 to the Competition and Consumer Act 2010 (Commonwealth),
  force as a law of Western Australia)

## Limitations

- **Not a live legal-currency service.** This is a point-in-time snapshot for
  deterministic testing only and may not reflect amendments made after the
  retrieval timestamp.
- The recorded official URLs use host `www.legislation.wa.gov.au`, which is on
  the closed two-host allowlist of exactly `legislation.wa.gov.au` and
  `www.legislation.wa.gov.au` (HTTPS).
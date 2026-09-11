# WA Legislation Fixture - Sale of Goods Act 1895 (WA)

Recorded, durable, version-controlled test/evaluation fixture for the
Phase 4/5 research corpus.

## What this is

- One shared **whole-Act official consolidated PDF** of the Sale of Goods
  Act 1895 (WA), captured byte-exact from `legislation.wa.gov.au`.
- A paired manifest recording provenance, version/currency, status, retrieval
  timestamp, SHA-256, and the pinned provisions.
- Per-section text under `provisions/`, derived by
  `scripts/derive_wa_provisions.py` from the recorded PDF.

## Files

| File | Purpose |
|---|---|
| `sale_of_goods_act_1895_consolidated_05-d0-06.pdf` | Official consolidated PDF, byte-exact |
| `sale_of_goods_act_1895_consolidated_05-d0-06.manifest.json` | Provenance + SHA-256 + pinpoints |
| `provisions/s_13[.txt\|.provision.json]` ... `s_16` | Derived section text + digests |

## Source and version

- **Act:** Sale of Goods Act 1895 (WA), Act No. 041 of 1895 (59Vict No 41),
  assent 12 Oct 1895.
- **Version:** Official consolidated version, suffix `05-d0-06`, document
  `mrdoc_19856`.
- **Currency:** start **11 Sep 2010**; end **Current** (in force at retrieval).
- **Retrieved (UTC):** `2026-09-08T02:16:40Z`
- **SHA-256:** `5e3a298c37d2d32aaad9a2eaaa61c44164b9144875316bf080b649a1b50081e1`

## Pinned provisions

- **s 13** - "Sale by description"
- **s 14** - "Implied conditions as to quality or fitness"
- **s 15** - "Sale by sample"
- **s 16** - "Goods must be ascertained"

## Limitations

- **Not a live legal-currency service.** This is a point-in-time snapshot for
  deterministic testing only and may not reflect amendments made after the
  retrieval timestamp.
- The recorded official URLs use host `www.legislation.wa.gov.au`, which is on
  the closed two-host allowlist of exactly `legislation.wa.gov.au` and
  `www.legislation.wa.gov.au` (HTTPS).
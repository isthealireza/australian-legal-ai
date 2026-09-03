# WA Legislation Staging Fixture — Road Traffic (Vehicles) Regulations 2014

This directory stages one byte-exact official WALW consolidated artifact. It is
not wired into a runtime root, API, UI, provider, auth, database, or answer
path.

## Source and version

- **Instrument:** Road Traffic (Vehicles) Regulations 2014 (WA)
- **Official source page:** https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_s45434.html
- **Consolidated version:** current from 1 Jul 2026; current; suffix `01-at0-00`
- **Document:** `mrdoc_49702`
- **Retrieved (UTC):** 2026-09-03T09:24:23Z
- **Artifact:** `road_traffic_vehicles_regulations_2014_consolidated_01-at0-00.pdf`
- **Length:** 2,149,832 bytes
- **SHA-256:** `912d05faaf5a1f1fd0b0f88751caa30fac36202ae484e6777336c5bb6b8e32af`

## Staging boundary

The manifest intentionally contains no provision or section records. The
existing corpus loader can stage and select a whole source without them; the
validator therefore refuses a pinpoint as `CITATION_NOT_FOUND`. No legal text
was copied or generated, and no `verified: true` claim was made.

Before merge or activation, the owner must accept the official source/version
and independently verify any deterministic extraction against this exact PDF.
The missing `pdftotext -layout`/pinned extraction capability and version/as-at
query selection are E0-B work if the corpus must answer versioned provisions.

Rollback is deleting this directory or removing it from the staging change; it
does not alter the active corpus because no runtime root or production contract
is changed.

# WA Legislation Fixture — Road Traffic Act 1974 (WA)

Recorded, durable, version-controlled test/evaluation fixture for the
owner-authorised Phase 4 fixture-recording task, governed by
[ADR 0013](../../../../docs/adr/0013-phase-4-research-evidence-packets.md) and the
[Phase 4 Slice 1 Scope Card](../../../../docs/execution/PHASE_4_SLICE_1_SCOPE_CARD.md).

## What this is

- One shared **whole-Act official consolidated PDF** of the Road Traffic Act 1974
  (WA), captured byte-exact from `legislation.wa.gov.au`.
- A paired manifest recording provenance, version/currency, status, retrieval
  timestamp, SHA-256, and the two target provisions as pinpoints.

This fixture records the complete consolidated official PDF. Sections 55 and 56
are recorded as manifest pinpoints only. No section-level source text was
extracted or separately recorded during this fixture-recording task; section-level
extraction and validation remain deferred to the authorised Phase 4 research
module.

## Files

| File | Purpose |
|---|---|
| `road_traffic_act_1974_consolidated_14-t0-00.pdf` | Official consolidated PDF, byte-exact |
| `road_traffic_act_1974_consolidated_14-t0-00.manifest.json` | Provenance + SHA-256 + pinpoints |

## Source and version

- **Act:** Road Traffic Act 1974 (WA), Act No. 059 of 1974, assent 3 Dec 1974.
- **Version:** Official consolidated version, suffix `14-t0-00`, document
  `mrdoc_48198`.
- **Currency:** start **10 Jan 2025**; end **Current** (in force at retrieval).
- **Official source URL:**
  `https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a703.html&view=consolidated`
- **Retrieved (UTC):** `2026-08-11T10:27:03Z`
- **SHA-256:** `61dbca2d8eddc33a3ebc759b8759886192efaa8b09440089541efd35ed19c525`

## Why sections 55 and 56

The Slice 1 vertical is WA parked/unattended motor **property-damage** claims.
The selected provisions are the driver's post-incident duties where property
damage occurs, taken verbatim from the official headings:

- **s 55** — "Driver in incident occasioning **property damage** to stop and give
  information".
- **s 56** — "Driver in incident occasioning bodily harm or **property damage** to
  report incident to police".

These are the core statutory obligations engaged when a parked or unattended
vehicle sustains property damage, making them the minimal, most
vertical-specific provisions for the first slice. (Adjacent s 54 concerns bodily
harm only; s 57 concerns owner identification duties — neither is the primary
property-damage duty, so both are excluded to keep the set minimal.)

## Limitations

- **Not a live legal-currency service.** This is a point-in-time snapshot for
  deterministic testing only and may not reflect amendments made after the
  retrieval timestamp.
- The fixture is the **whole Act**; it is not per-section text and requires the
  Phase 4 module for pinpoint extraction and validation.
- The recorded official URLs use host `www.legislation.wa.gov.au`. ADR 0013 now
  defines a closed two-host allowlist of exactly `legislation.wa.gov.au` and
  `www.legislation.wa.gov.au` (HTTPS); the `www` host is included because the
  official WA Legislation homepage and resolved official document URLs use it.
  No wildcard or other subdomain is trusted, and the recorded `www` URLs are
  kept faithful (not rewritten to the apex host).

## Integrity

SHA-256 is computed over the exact stored file bytes (binary PDF; no
normalisation, re-serialisation, or trailing-newline convention). Recompute with:

```
sha256sum road_traffic_act_1974_consolidated_14-t0-00.pdf
```

# Corpus-Expansion WA Slice — Independent PDF Digest Verification

**Date:** 2026-09-08
**Verifier method:** Each PDF was downloaded a second time, fresh, straight from
the official WA Legislation host (`www.legislation.wa.gov.au`, the only
permitted host), to a temporary directory **outside the repository**, and its
SHA-256 was recomputed from those independent bytes. The result is compared
against the digest recorded in the committed fixture manifest (the manifest
digest was itself computed at first capture from the same official source).
Byte-for-byte equality between the two independent captures is the evidence
that the recorded fixture is the official consolidated PDF and is unmodified.

The external review gate (`scripts/deepseek_review.py`) refuses to transmit
binary files, so the PDFs themselves cannot appear in a review bundle. This
file exists so that the SHA-256 references for the three PDFs are available to
reviewers without transmitting binaries.

| Act | Official page | Filename | Content-Length | Manifest sha256 (= independent re-download sha256) | Independent match |
|---|---|---|---|---|---|
| Building and Construction Industry (Security of Payment) Act 2021 | https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a147300.html | `building_and_construction_industry_security_of_payment_act_2021_consolidated_00-e0-00.pdf` | 767,632 | `9d78bc1fc594d61af5ec095c03d18b7c266aeb8fe52fd776611dee57574edd5b` | MATCH |
| Motor Vehicle Dealers Act 1973 | https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a525.html | `motor_vehicle_dealers_act_1973_consolidated_06-k0-01.pdf` | 607,971 | `d91d26a14da9be42c0c477c4ae15a8e9171d11ae68ea5fc77889042a2a1e9990` | MATCH |
| Owner-Drivers (Contracts and Disputes) Act 2007 | https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a146614.html | `owner_drivers_contracts_and_disputes_act_2007_consolidated_01-g0-00.pdf` | 505,314 | `03071c9fe15dfdc3a8c26ebfd9027f5ff6044f91c83e0455ace5b5ac40b43bad` | MATCH |

All three matched byte-for-byte (independent re-download digest == committed
manifest digest).

Recorded fixtures are a point-in-time snapshot for deterministic testing only.
They are NOT a live legal-currency service.
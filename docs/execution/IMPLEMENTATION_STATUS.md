# Implementation Status — Phase Ledger

**Last updated:** 2026-07-28

## Phase status

| Phase | Status |
|---|---|
| Phase 0 — Repository audit and product-pivot decision | **in progress** |
| Phase 1 — Generic matter core | not started |
| Phase 2 — Playbook registry and WA motor playbook | not started |
| Phase 3 — Evidence vault extension | not started |
| Phase 4 — Research and evidence packets | not started |
| Phase 5 — Drafting with mock model | not started |
| Phase 6 — Approval service | not started |
| Phase 7 — Communication ingestion and draft replies | not started |
| Phase 8 — Approved email sending | not started |
| Phase 9 — Durable workflow ADR and implementation | not started |
| Phase 10 — Private-alpha API and UI | not started |
| Phase 11 — Live model evaluation | not started |
| Phase 12 — Private-alpha deployment preparation | not started |

## Current approved scope

Phase 0 documentation only, as approved by the repository owner:

- Create `docs/adr/0009-casework-os-product-pivot.md`
- Create `docs/execution/CASEWORK_OS_AUDIT.md`
- Create `docs/execution/CASEWORK_OS_ROADMAP.md`
- Create `docs/execution/IMPLEMENTATION_STATUS.md`
- Modify `docs/adr/README.md` only

No product code. No Phase 1. No new repository. No weakening of existing
legal research, provenance, FRL, parsing, legislation, security, or test
capabilities. No push, merge, or PR unless separately authorised.

## Branch and baseline

- **Branch:** `docs/phase-0-casework-os-audit`
- **Baseline commit:** `1ef936fab780f5d03867a3c9beffa4e5fd859b47` (`origin/main`, PR #7 merge)
- **Resulting commit:** recorded in the Phase 0 completion report after local commit

## Blockers and approval gates

1. ADR 0009 remains **Proposed** until merged/accepted on `main`.
2. Phase 1 product code blocked until ADR 0009 is Accepted **and** owner
   authorises a separate `MVP_ROADMAP.md` amendment.
3. Every L3+ capability blocked until a dedicated ADR and controls exist.
4. Live providers, OAuth, real personal data, and external deployment require
   explicit owner gates.
5. No autonomous admission, settlement, signature, court filing, police
   submission, insurance submission, or external communication.

## Objective (Phase 0)

Complete documentation-only Phase 0 deliverables on the branch above.

## Decisions (Phase 0)

- Extend repository in place; preserve FRL, provenance, EPUB, legislation modules
- First operational playbook: `wa_motor_property_damage_v1`
- Explicit state machine before any Temporal ADR
- L3+ external actions remain gated behind dedicated ADRs and owner credentials

## Assumptions

- ADR number 0009 remains free on `origin/main` (verified before writing)
- Repository facts match the audit baseline `1ef936f`
- Phase 0 docs may be locally committed; push/PR only if owner authorises

## Validation evidence

Commands required before Phase 0 completion:

```text
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy .
uv run --locked pytest -q --ignore=tests/integration
git diff --check
git diff main...HEAD --stat
```

Exact results are recorded in the Phase 0 completion report after those
commands run on the final documentation commit.

## Residual risks

- Stale README relative to implemented Sprint 1.x code
- Governance precedence risk if Phase 1 starts without `MVP_ROADMAP.md` amendment
- L3/L4 email phases must not ship without dedicated controls
- Integration/CI database coverage remains thin for future matter isolation

## Exact next action after Phase 0

Stop. Do not start Phase 1. Await owner PR review of ADR 0009 and a separate
owner-approved `MVP_ROADMAP.md` amendment before any product code.

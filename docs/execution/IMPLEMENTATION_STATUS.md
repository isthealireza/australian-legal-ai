# Implementation Status — Phase Ledger

**Last updated:** 2026-07-28

## Phase status

| Phase | Status |
|---|---|
| Phase 0 — Repository audit and product-pivot decision | **Completed** (merged to `main` @ `9cd74bad53f774dabaf976cbd47325335bf133d9`, PR #8) |
| Phase 1 — Generic matter core | **In Progress** |
| Phase 2 — Playbook registry and WA motor playbook | Not Started |
| Phase 3 — Evidence vault extension | Not Started |
| Phase 4 — Research and evidence packets | Not Started |
| Phase 5 — Drafting with mock model | Not Started |
| Phase 6 — Approval service | Not Started |
| Phase 7 — Communication ingestion and draft replies | Not Started |
| Phase 8 — Approved email sending | Not Started |
| Phase 9 — Durable workflow ADR and implementation | Not Started |
| Phase 10 — Private-alpha API and UI | Not Started |
| Phase 11 — Live model evaluation | Not Started |
| Phase 12 — Private-alpha deployment preparation | Not Started |

## Current approved scope

- ADR 0009: **Accepted** (2026-07-28)
- `MVP_ROADMAP.md` §11A: Casework Phase 1 foundation authorised after approved plan
- Phase 1 final corrected plan: **owner-approved for implementation**
- Phase 1 boundaries: Generic Casework Core only (L0–L2); no playbooks, LLM, email,
  evidence binaries, FastAPI/UI, pgvector, L3+, or real client data
- Phase 2: **Not Started**

## Branch and baseline

- **Branch:** `feat/phase-1-casework-core`
- **Starting main SHA:** `9cd74bad53f774dabaf976cbd47325335bf133d9`
- **Active slice:** domain types, state machine, and authority policy

## Blockers and approval gates

1. Push/PR/merge not authorised by the Phase 1 implementation approval alone until
   owner requests publication.
2. Phase 1 must not be marked **Completed** until the implementation PR is merged;
   end-of-branch status is **Implementation Complete; Merge Pending**.
3. Every L3+ capability blocked until a dedicated ADR and controls exist.
4. No autonomous admission, settlement, signature, court filing, police
   submission, insurance submission, or external communication.

## Authority precedence

```text
CLAUDE.md
  → docs/execution/MVP_ROADMAP.md (incl. §11A)
  → AGENTS.md
  → LEGAL_AI_MASTER_BLUEPRINT.md (north star; does not override CLAUDE/MVP)
  → ADR 0009
  → docs/execution/CASEWORK_OS_ROADMAP.md (Casework workstreams only)
  → approved Phase 1 plan
```

## Exact next action

Continue Phase 1 slices on `feat/phase-1-casework-core` within the approved file
and capability boundary. Do not start Phase 2.

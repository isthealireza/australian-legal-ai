# ADR 0011: Governance and engineering terminology

- Status: Accepted
- Date: 2026-08-06
- Accepted: 2026-08-06

## Context

The public tracked tree combines substantive Agentic Legal AI product
architecture with repository-development instructions that prescribe or name
particular development tools. Product terminology about artificial
intelligence, agents, models, providers, grounding, retrieval, evidence,
verification, prompt-injection defence, safety, and action authority is
technically necessary and must remain. Development governance does not need to
identify a particular editor, model, assistant, or implementation tool.

The root constitution requires an accepted ADR and a new governance tag for
governance changes. The execution roadmap also freezes planning-document
revisions except where an ADR records a concrete execution blocker. Public
tool-specific development terminology is the concrete blocker addressed here:
it prevents consistent, role-based engineering governance and conflates
development workflow with product architecture.

## Decision

This decision takes effect prospectively on 2026-08-06. It does not assert
that these governance terms or filenames applied before that date.

1. Public engineering governance will use professional, role-based terminology
   such as Project Owner, Architecture and Design Review, Implementation
   Workflow, Independent Review, Development Environment Security Validation,
   Merge Approval, and Legal Review.
2. Rename the root governance files:
   - the root constitution to `PROJECT_GOVERNANCE.md`;
   - the engineering execution rules to `ENGINEERING_WORKFLOW.md`.
3. Update every current-tree cross-reference atomically while preserving the
   existing authority order:
   `PROJECT_GOVERNANCE.md` → `docs/execution/MVP_ROADMAP.md` →
   `ENGINEERING_WORKFLOW.md` → approved task instructions → other repository
   documents.
4. Apply a limited exception to the `MVP_ROADMAP.md` planning freeze solely to
   replace development-tool attribution and update governance references. Its
   scope, sprint requirements, acceptance criteria, product architecture, and
   release gates remain unchanged.
5. Remove named development-tool attribution from the current tracked tree,
   including tool-specific target directories and public ignore entries.
6. Preserve every substantive product architecture, legal, safety, security,
   privacy, grounding, provenance, verification, fail-closed, and action-
   authority requirement. Product references to artificial intelligence,
   agents, models, providers, prompts, and automation remain where technically
   necessary.
7. Changes are forward-only. Published Git history and historical GitHub
   metadata will not be rewritten. No statement will claim or imply that the
   repository was developed entirely manually, that automated development
   tools never participated, or that historical provenance was erased.
8. After the standardization Pull Request is separately authorised, merged,
   and its resulting `main` commit verified, the owner may separately authorise
   creation of annotated tag `governance-v1.1.0` on that exact commit. The tag
   must not be created before merge and must not move or replace an existing
   tag.

## Consequences

- Engineering responsibilities and controls remain enforceable without naming
  development vendors or tools.
- The Agentic Legal AI product architecture and all safety boundaries remain
  unchanged.
- Historical development provenance remains available in existing Git objects
  and historical GitHub metadata.
- No source code, tests, migrations, schemas, APIs, dependencies, application
  behaviour, or product security behaviour changes under this decision.

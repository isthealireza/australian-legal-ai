# Australian Legal AI OS
## Master Architecture, Governance, Engineering Roadmap and Delivery Plan

**Language:** English (authoritative edition; the original Persian draft is archived at `docs/archive/LEGAL_AI_MASTER_BLUEPRINT_FA.md`)
**Status:** Master Project Blueprint — North Star architecture
**Version:** 1.1.0 (English edition of v1.0.0; content-equivalent)
**Date:** 20 July 2026
**Primary jurisdictional focus:** Australia; initial implementation priority: Commonwealth and Western Australia
**Repository role:** Project-level source of truth for target architecture, delivery sequence, tooling responsibilities, security boundaries, release gates, and unresolved dependencies.
**Execution note:** Current build scope is defined by `docs/execution/MVP_ROADMAP.md`, which supersedes this document's delivery sequence but never its security, grounding, privacy, provenance, evaluation, or non-lawyer requirements.

---

# 1. Executive Summary

This project is NOT a general-purpose chatbot that answers legal questions from model memory. The target product is a **Private Australian Legal Operations Copilot** for organisational legal and commercial work. At full build-out it can:

- create and manage matters;
- identify jurisdiction and forum;
- analyse contracts and documents;
- perform legal research;
- retrieve and version legislation, delegated legislation, cases, court rules, practice notes, and regulator guidance;
- manage claims, disputes, notices, and deadlines;
- produce drafts, redlines, chronologies, risk registers, legal memoranda, and negotiation packs;
- preserve evidence and provenance;
- enforce precise, replay-proof approvals;
- advance workflows to the extent permitted;
- and **never** present itself as a lawyer or autonomously perform any binding action, filing, service, signature, settlement, waiver, or sensitive disclosure.

**Foundational principle:**

> The language model is not a source of law. The model analyses only verified evidence packets, current policies, and bounded tools.

The correct goal is not "knowing all the law." The correct goal is a system that:

1. locates official, current sources;
2. checks jurisdiction, effective date, amendments, commencement, repeal, and transition;
3. ties every legal proposition to a source and pinpoint;
4. stops when retrieval or verification fails;
5. never hides uncertainty;
6. escalates to human review and independent verification with intensity proportional to risk.

---

# 2. Product Mission

Target domains:

Contract review and redlining · Contract drafting · Commercial legal research · Contractual claims · Dispute and pre-litigation preparation · Notice preparation · Settlement preparation · Evidence and document analysis · Chronology generation · Obligation and deadline tracking · Legal and commercial risk management · Matter management · Regulatory and court-facing preparation · Internal legal operations · Policy and playbook management · Knowledge and precedent management · Audit, approval and governance.

## 2.1 Non-Goals

The system, in all planned versions:

- is not a law firm;
- is not an admitted lawyer;
- does not replace advice and review by a qualified human;
- does not use model memory as authority;
- does not issue definitive legal findings without a verified source;
- does not autonomously sign, file, serve, settle, pay, waive, or bind;
- does not auto-promote generated skills or policies into production;
- has no unrestricted shell, unrestricted network, or unrestricted filesystem tool;
- sends no privileged or sensitive information to any unapproved provider.

---

# 3. Operating Model: Humans and Tools

## 3.1 Project Owner

The repository owner is the human user and final decision-maker. Responsibilities: approve scope and business requirements; maintain the repository and branches; run tasks; review diffs; approve merges; decide provider, budget, data residency, and retention; designate authorised people; obtain real legal advice where required; approve production releases.

## 3.2 Planning Assistant (architecture/design AI)

Roles: Software Architect · Full-Stack Technical Lead · AI Systems Architect · Security Reviewer · Legal AI Governance Adviser · Task Designer · Acceptance-Criteria Designer · Diff and Evidence Reviewer · Step-by-Step Technical Coach.

By default the planning assistant does not write project code in place of the owner. Its job is task design, output review, risk detection, explanation, and architectural consistency.

## 3.3 Codex — Primary Implementation Agent

**Codex executes repository-level changes.** Suitable for: multi-file builds; refactors; test generation; running lint, type checks, and tests; producing diffs; providing terminal evidence; working in an isolated branch or worktree; fixing review findings; preparing review-ready changes.

> Rule: Codex is an executor, not an architecture decision-maker.

Every Codex task MUST include: a bounded goal; in-scope and out-of-scope lists; allowed files; acceptance criteria; test commands; forbidden changes; rollback instructions; evidence requirements.

## 3.4 Cursor with Claude — IDE and Interactive Reviewer

Cursor is used for: fast repository exploration; understanding file relationships; questions about a specific line or function; manual diff review; architecture review; security review; pair programming; very small urgent fixes; explaining code and tests.

Cursor is NOT responsible for autonomously building an entire phase.

## 3.5 Real Claude Code — Runtime-Specific Security Testing

Using Claude inside Cursor is NOT equivalent to the Claude Code runtime. Test ONLY in real Claude Code: `.claude/settings.json`; permission modes; PreToolUse/PostToolUse hooks; managed settings; sandbox; filesystem/network restrictions; MCP tool names and schemas; custom agents; skills; `bypassPermissions` posture; hook failure behaviour.

Preferred test environment: WSL2/Linux, or a Linux container/VM. Do not rely on native Windows as a security boundary.

## 3.6 Official Tool Workflow

| Activity | Primary tool |
|---|---|
| Architecture and task design | Planning assistant + owner |
| Repository implementation | Codex |
| Tests and evidence | Codex |
| Manual diff review | Cursor + owner |
| Adversarial review | Cursor/Claude or an independent Codex task |
| Review remediation | Codex |
| Claude-specific security testing | Claude Code on WSL2/Linux |
| Merge approval | Owner |
| Legal approval | Qualified human/lawyer |

Two agents must never hold simultaneous write access to the same branch and files.

---

# 4. Root Operating Constitution

The governance file MUST exist at repository root with exactly this name: `CLAUDE.md`.

Files such as `CLAUDE.reviewed.md`, `CLAUDE_v3.md`, or `CLAUDE-final-copy.md` are NOT the root constitution. Superseded versions live only in `docs/archive/governance/`.

## 4.1 The Triad

```text
Capability ≠ Authority ≠ Risk
```

- **Capability:** what the system can technically do.
- **Authority:** what it is permitted to execute.
- **Risk:** how sensitive the artifact or matter is.

None substitutes for another.

## 4.2 Grounding

```text
No grounding, no finding.
No verified source, no legal proposition.
```

## 4.3 Determinism

Perform with deterministic tools, never with a model: hashing · parsing · diffing · arithmetic · deadline calculations · schema validation · file type detection · source-version comparison · approval comparison · recipient matching · document version matching. Bounded judgment and interpretation are performed by the agent.

## 4.4 Fail-Closed

If any required control is missing, the sensitive action stops: retrieval · source verification · approval authentication · audit sink · verifier · policy service · evidence hash · privacy classification · endpoint validation · hook/permission control · MCP schema validation.

---

# 5. Action Authority: L0–L6

| Level | Definition | AI execution |
|---|---|---|
| L0 | Read-only research | Automatic, logged |
| L1 | Internal reversible action | Automatic, logged |
| L2 | Draft creation | Only in review locations, marked DRAFT |
| L3 | Routine external dispatch under standing authority | Disabled by default; only with formal delegation and technical controls |
| L4 | Case-specific external dispatch | Only with precise, authenticated, artifact-bound approval; otherwise human dispatch |
| L5 | Legally/financially binding action | Human decision and execution only |
| L6 | Filing, service, signature, court/regulator representation, evidence destruction/alteration, privileged disclosure | NEVER autonomously executable |

## 5.1 Anti-Decomposition Rule

A high-risk action must never be split into multiple low-risk actions to obtain a lower classification.

## 5.2 Examples

```text
Draft affidavit           = L2
File affidavit            = L6
Prepare settlement option = L2
Accept settlement         = L5
Draft termination notice  = L2
Issue binding termination = L5/L6 depending on effect and channel
```

---

# 6. Risk Classification: R0–R4

| Risk | Definition |
|---|---|
| R0 | Administrative/routine |
| R1 | Low risk |
| R2 | Material legal or commercial matter |
| R3 | High legal/commercial/reputational risk |
| R4 | Court, regulator, evidence, privilege, sensitive data, or rights-critical |

Risk is assigned at intake and reassessed whenever scope changes.

Example: `Draft affidavit = L2 / R4` · `File affidavit = L6 / R4`

---

# 7. Verification Depth

**R0–R1:** one bounded agent; source verification for every legal proposition; grounding check; no external effect.

**R2:** deterministic checks; source/currency check; citation existence and pinpoint check; human review before operational reliance.

**R3:** all of R2; independent fresh-context verifier; the drafter may not self-certify final output; human review.

**R4:** all of R3; adversarial/red-team review; qualified human or admitted practitioner review; forum-specific disclosure and procedural checks.

> Note: citation existence can be verified deterministically. Whether a citation actually supports a legal proposition is interpretation and is never fully deterministic.

---

# 8. High-Level System Architecture

```text
[Web UI / Operator Interface]
              |
        [API Gateway]
              |
      [Identity & Access]
              |
       [Matter Service]
              |
   [Workflow Orchestrator]
      /       |        \
[Policy] [Agent Runtime] [Approval Service]
    |          |              |
    |     [Bounded Tools]      |
    |          |              |
    +------[Audit/Event Store]-+
               |
        [Retrieval Service]
        /       |        \
 [Legal DB] [Matter DB] [Object Storage]
        |
 [Official Source Supply Chain]
```

## 8.1 Architectural Principle

Workflow-first, policy-enforced, retrieval-grounded, bounded agents.

NOT: `One autonomous agent + shell + browser + email + memory`.

## 8.2 Initial Stack

**Backend:** Python 3.13 · FastAPI · Pydantic · PostgreSQL · SQLAlchemy or an equivalent typed data layer · Alembic migrations.

**Frontend:** Node.js LTS · Next.js · TypeScript · accessible component system · secure server-side session handling.

**Retrieval (MVP):** PostgreSQL full-text/BM25-compatible lexical retrieval where adequate · pgvector · metadata filtering · reranking. **Scale-up:** OpenSearch/Elasticsearch for advanced hybrid retrieval, only when justified.

**Workflow:** start with an explicit application state machine and minimal orchestration; no premature frameworks. Adopt LangGraph (or an equivalent bounded agent graph) only when durable pause/resume and long-running workflows are proven necessary. Adopt Temporal only when an enterprise durable outer workflow is genuinely required. Never adopt LangGraph and Temporal simultaneously in the first implementation.

**Policy:** MVP is a typed in-app policy engine, deny-by-default, comprehensively tested. Adopt OPA or Cedar later only when multiple independent policy-enforcement points justify a separate policy decision service.

**Storage:** PostgreSQL for structured metadata, matters, users, approvals, policies · S3-compatible object storage for original and derived documents · append-only/tamper-evident audit store · secrets manager · KMS-managed encryption · matter-specific access boundaries.

**Observability:** OpenTelemetry · metrics · security events · privacy-safe traces · incident alerts.

---

# 9. Repository Architecture (target)

```text
australian-legal-ai/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── SECURITY.md
├── CONTRIBUTING.md
├── pyproject.toml
├── uv.lock
├── package.json
├── pnpm-lock.yaml
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .cursor/            (rules/, commands/)
├── .claude/            (settings.json, hooks/, agents/, rules/, skills/)
├── apps/               (api/, web/, workers/)
├── packages/           (contracts/, policy/, observability/, ui/)
├── workflows/          (router.yaml, matter_intake.md, conflict_check.md,
│                        contract_review.md, legal_research.md,
│                        final_verification.md, court_facing_review.md)
├── policies/           (approval, ai_disclosure, change_control,
│                        confidentiality_privilege, conflicts,
│                        data_classification, delegation_of_authority,
│                        incident_response, injection_defence,
│                        model_governance, playbook, privacy,
│                        risk_classification, retention, source_integrity)
├── sources/au/         (registry/, commonwealth/, wa/, courts/, regulators/)
├── schemas/            (approval-record, legal-source, matter,
│                        finding, audit-event — *.schema.json)
├── tools/              (hashing/, document/, deadline/, citation/, approval/)
├── evals/              (golden/, adversarial/, regression/, graders/,
│                        datasets/, release-gates/)
├── tests/              (unit/, integration/, security/, e2e/)
├── docs/               (adr/, architecture/, threat-model/, runbooks/,
│                        archive/, execution/)
├── matters/README.md
├── logs/audit/
└── proposals/workflow-amendments/
```

This structure is the end-state target. Do NOT create every folder in the first commit; create folders only when a phase needs them.

---

# 10. Matter Model

Every matter includes at minimum: `matter_id` · title · matter type · jurisdiction · governing law · forum · procedural posture · parties · related entities · capacities · conflict-check status · risk class · deadline flags · privilege status · data classification · responsible human · authorised reviewers · source snapshot/version · open issues · approvals · audit references · retention/hold status.

## 10.1 Matter Isolation

- Cross-matter retrieval is prohibited unless a policy explicitly allows it.
- PostgreSQL Row-Level Security.
- Object-storage prefix isolation.
- Matter-scoped encryption context where possible.
- Traces and eval data contain no privileged matter content.
- Memory is matter-scoped only.

---

# 11. Matter Intake Workflow

Before any substantive processing:

1. create matter ID; 2. identify parties and capacities; 3. jurisdiction and governing law; 4. forum and procedural posture; 5. Commonwealth/State/Territory analysis; 6. cross-border elements; 7. conflict and restricted-matter screening; 8. privilege/confidentiality/privacy classification; 9. deadline and limitation flags; 10. evidence and preservation flags; 11. insurance notification consideration; 12. dispute-resolution prerequisites; 13. preliminary L/R classification; 14. responsible human assignment.

## 11.1 Emergency Deadline Mode

If a limitation, appeal, filing, service, or contractual-notice deadline may be near: do not wait for full intake; immediately alert an authorised human; mark the deadline provisional; record trigger date, timezone, and business-day assumptions; run the deterministic calculator; a human confirms any filing-critical date.

---

# 12. Conflict Check

Check: current clients · former clients · adverse parties · related entities · directors/officers · related matters · confidential information · personal interests · information barriers · restricted matters.

A name match alone is not a conflict. Process:

```text
Candidate match → identity resolution → relationship analysis
→ information-access analysis → human confirmation
→ conflict/consent/barrier decision
```

Ethical wall, consent, or refusal decisions are made only by a qualified human.

---

# 13. Data Classification

Classes: PUBLIC · INTERNAL · CONFIDENTIAL · PERSONAL · SENSITIVE · PRIVILEGED · WITHOUT_PREJUDICE · SUPPRESSED · STATUTORY_SECRET · COMPELLED_PRODUCTION · EVIDENCE_HOLD.

## 13.1 Processing Rule

Before any external transmission: data classification · processor approval · purpose validation · data minimisation · redaction/pseudonymisation where suitable · logging of destination and legal basis.

Local deterministic intake may perform the minimum necessary processing: malware scan · hash · file type detection · metadata extraction · local OCR · preliminary classification · redaction.

---

# 14. Privacy, Privilege and Confidentiality

These concepts are distinct and must never be conflated: privacy · confidentiality · client legal privilege · without-prejudice protection · suppression · statutory secrecy · compelled-production restrictions.

Privilege is never accepted on a label alone. Assess: holder · communication participants · dominant purpose · lawyer/client capacity · confidentiality · forum · waiver risk · attachment and chain context.

## 14.1 AI Provider Due Diligence

For every provider assess: data retention · training usage · data residency · subcontractors · administrator access · encryption · deletion · incident notification · audit rights · contractual confidentiality · cross-border disclosure · model logging · trace storage.

Public AI tools are prohibited for personal, sensitive, or privileged information unless an explicit policy and legal assessment approve otherwise.

---

# 15. Legal Source Supply Chain

## 15.1 Source Priority

Authority is determined per proposition and jurisdiction, not by a fixed list. Possible sources: Constitution · legislation · delegated legislation · commencement instruments · transitional provisions · court/tribunal rules · practice notes · binding appellate authority · persuasive authority · official regulator guidance · reputable secondary commentary.

Regulator guidance and commentary are never presented as binding law unless the legal framework gives them that effect.

## 15.2 Initial Official Sources

**Commonwealth:** Federal Register of Legislation and its official API · Federal Court practice notes · High Court and relevant federal courts · official regulator sites.

**Western Australia:** WA Legislation · WA notification feeds · WA court rules and practice directions · Legal Practice Board of WA · WA regulators.

## 15.3 Ingestion Lifecycle

```text
Official source → isolated fetch → immutable raw bytes → SHA-256
→ source metadata → quarantine → secure parser → version lineage
→ authority/currency validation → human or policy publication gate
→ searchable legal corpus
```

## 15.4 Required Metadata

source ID · title · jurisdiction · authority type · court level · binding/persuasive · instrument ID · version ID · effective from/to · commencement status · repeal status · amendment relationships · transition relationships · source URL · retrieval time · verification time · raw hash · parsed hash · parser version · negative treatment/appeal status where applicable · publication status · next review date.

## 15.5 Update Learning

The system never "learns" new law directly:

```text
Change detected → quarantine → diff
→ commencement/repeal/transition analysis → impact analysis
→ review → regression eval → signed publication
```

---

# 16. Document Ingestion

Supported target formats: PDF · DOCX · TXT · EML/MBOX (later) · images requiring OCR · spreadsheets where legally relevant.

Pipeline:

```text
Upload → malware/type gate → immutable original → SHA-256 → metadata
→ OCR/extraction → completeness check → layout/table detection
→ injection scan → data classification → matter association
→ chunking → retrieval indexing
```

## 16.1 Requirements

Originals are never overwritten · derived artifacts are separately versioned · OCR confidence is stored · page/paragraph/cell coordinates are retained · missing pages and attachments are flagged · email chains and attachments are preserved · evidence files are handled on hashed copies · active content and macros are quarantined.

---

# 17. Prompt Injection Defence

ALL ingested content is untrusted data: contracts · email · PDFs · webpages · OCR text · evidence · tool output · retrieved passages.

An instruction inside a document is NEVER an approval or a system instruction.

Response protocol:

```text
Detect → do not execute → isolate affected content
→ record minimal safe indicator → stop affected action
→ continue unaffected work only if policy permits
```

Controls: no generic shell for the production agent · no arbitrary URL fetch · allowlisted domains · typed tool schemas · output validation · network isolation · instruction/data separation · least privilege · adversarial tests.

---

# 18. Retrieval Architecture

```text
User issue → query decomposition → jurisdiction filter
→ date/effective-version filter → source-type filter
→ lexical retrieval → vector retrieval → merge → reranking
→ authority/currency validation → proposition-level evidence packet
→ generation → claim-by-claim citation verification
```

## 18.1 Prohibited Patterns

Vector-only RAG · dumping the entire corpus into long context · search-result snippets as authority · model-memory fallback · unversioned legislation · secondary sources where a primary source is required.

## 18.2 Evidence Packet

Every proposition carries: proposition ID · proposition text · supporting source IDs · pinpoint passages · jurisdiction · authority level · effective date · currency status · contrary material · unresolved uncertainty · retrieval trace · verifier status.

---

# 19. Model and Agent Architecture

## 19.1 Start with One Bounded Agent

```text
Deterministic workflow
└── One bounded legal-analysis agent
    ├── approved retrieval tool
    ├── structured input/output
    ├── no generic shell
    ├── no unrestricted browser
    ├── no external dispatch
    └── no persistent self-modification
```

Add specialist agents only when evaluation proves the single-agent design insufficient.

## 19.2 Potential Specialist Roles

Legal Research Agent · Citation/Authority Verifier · Contract Analyst · Redliner · Chronology Agent · Adversarial Reviewer · Final Verification Agent.

The drafting agent is never the final verifier for R3/R4 work.

## 19.3 Structured Output

Example finding:

```json
{
  "finding_id": "F-001",
  "proposition": "...",
  "jurisdiction": ["AU-CTH", "AU-WA"],
  "source_ids": ["SRC-..."],
  "pinpoints": ["..."],
  "authority_status": "binding",
  "effective_date": "2026-07-20",
  "confidence": "high",
  "uncertainties": [],
  "requires_human_review": true
}
```

## 19.4 Provider Neutrality

Domain code must never bind directly to one provider. Maintain a model registry: provider · model ID · snapshot · approved use cases · data classification ceiling · context limits · tools allowed · evaluation version · approval date · rollback model. Every model upgrade requires regression evaluation and a release gate.

---

# 20. Memory and Continuous Learning

Four memory types:

- **20.1 Session memory:** ephemeral; expires; not authoritative.
- **20.2 Matter memory:** scoped to one matter; access controlled; versioned; never crosses matters.
- **20.3 Organisational knowledge:** approved templates; clause playbooks; policies; approved precedents; reviewed FAQs.
- **20.4 Skill registry:** versioned; signed/reviewed; tested; never self-promoted.

Learning pipeline:

```text
Observed issue → candidate improvement → proposal → quarantine
→ security review → adversarial eval → regression eval
→ authorised maintainer approval → signed release
```

No agent may directly rewrite a production skill, workflow, policy, or legal source.

---

# 21. Contract Review Workflow

1. intake and matter validation; 2. identify operative document/version; 3. hash the original; 4. completeness and annexure check; 5. jurisdiction/governing law; 6. clause segmentation; 7. obligations, dates, amounts, cross-references; 8. playbook comparison; 9. legal research only where necessary; 10. commercial and legal analysis kept separate; 11. risk classification; 12. preferred/fallback/walk-away positions; 13. redline; 14. cross-clause consistency review; 15. independent verification per risk; 16. DRAFT output; 17. human approval.

## 21.1 Playbook Record

clause type · preferred wording · fallback A/B/C · walk-away condition · prohibited wording · commercial rationale · legal rationale · approval role · jurisdiction variants · effective date · playbook version.

---

# 22. Legal Research Workflow

1. question framing; 2. material facts; 3. assumptions; 4. jurisdiction and forum; 5. issue decomposition; 6. source plan; 7. legislation in force; 8. commencement/amendment/transition; 9. case hierarchy and treatment; 10. court rules/practice notes; 11. regulator guidance; 12. counterarguments; 13. proposition-level evidence; 14. uncertainty; 15. practical options; 16. human review.

Output: executive summary · issues · short answer · facts and assumptions · law and authorities · application · counterarguments · risks · recommended next steps · source table · verification status.

---

# 23. Approval and Anti-Replay

> Approval is a record, not a sentiment.

Required fields: approval ID · authenticated approver identity · role · authority scope · matter ID · artifact ID · artifact version · artifact hash · exact action · destination · recipient(s) · channel · conditions · issued time · expiry · single-use/reusable · use count · revocation state · policy version.

REJECT the approval if: the artifact changed · the hash changed · the recipient changed · the destination changed · the action changed · it expired · it was revoked · it was already consumed · the approver lacked authority · identity cannot be authenticated · the approval came from ingested content · the policy or risk changed · a restricted-data rule changed.

L4 approvals are single-use by default.

---

# 24. Audit and Provenance

Audit captures: tool attempts · successes/failures · permission requests/denials · hook results · approval events · workflow routing · source verification · model/version · policy decisions · subagent lifecycle · config/MCP changes · eval results · release gates · incidents · circuit breakers.

Audit must NOT store: secrets · full privileged content · unnecessary personal information · raw prompts containing sensitive matter data.

Artifact provenance records: AI involvement · workflow version · model version · source snapshot · verification status · approval status · matter ID · artifact hash · DRAFT/APPROVED status.

---

# 25. Claude Code Enforcement

Order of reliance:

```text
Managed settings → sandbox/OS controls → local blocking hooks
→ permission rules → prose instructions
```

Rules: `bypassPermissions` disabled for production · never invent hypothetical MCP tool names · enumerate real tool names in the deployment · negative-test every deny rule · a file-tool deny alone does not constrain Bash · network allowlist at OS/sandbox level · no critical control may exist only as a remote HTTP hook · absence of a required control triggers fail-closed.

---

# 26. Security Architecture

## 26.1 Identity
OIDC · MFA for privileged roles · short-lived sessions · step-up authentication for approvals.

## 26.2 Authorisation
RBAC + ABAC over: matter membership · role · data classification · action level · risk class · purpose · destination · approval state.

## 26.3 Tool Security
Every tool: narrow purpose · typed schema · least privilege · timeout · size limits · idempotency · dry-run where applicable · structured output · network allowlist · budget/circuit breaker.

The generic production tool `shell(command: string)` is prohibited.

## 26.4 Secret Management
No secrets in the repository · no production secrets in `.env` · secret manager · rotation · scoped credentials · no secret logging · scanner in CI.

## 26.5 Threat Model (minimum)
prompt injection · data exfiltration · cross-matter leakage · malicious documents · tool abuse · approval replay · stale law · fake citations · compromised provider · poisoned memory · supply-chain compromise · insider misuse · audit tampering · evidence modification · insecure logs.

---

# 27. Evals and Release Gates

## 27.1 Metrics
retrieval recall@K · citation precision · pinpoint accuracy · authority correctness · legal currency · jurisdiction accuracy · unsupported claim rate · deadline accuracy · injection containment · policy violation rate · cross-matter leakage · human override rate · latency · cost · trace completeness.

## 27.2 Adversarial Cases
repealed law · future amendment not commenced · transitional provisions · incomplete OCR · missing annexures · fake cases · real citations that do not support the claim · negative treatment · wrong jurisdiction · prompt injection in a contract · prompt injection in an email · malicious tool output · same-name parties · deadlines around holidays/weekends · hash-mismatched approvals · expired approvals · approval replay · provider timeouts · audit failure · retrieval failure · cross-matter access · privileged text in logs.

## 27.3 Release Gate
Material changes requiring a gate: CLAUDE.md · AGENTS.md · rules · skills · workflows · agents · tools · models · source parsers · MCP servers · hooks · permissions · data schemas · policy engine.

Release evidence: full test suite · security tests · eval results · diff · migration plan · rollback plan · unresolved risks · approval owner.

---

# 28. Frontend Product Features (target)

- **28.1 Matter Dashboard:** matter list · risk · jurisdiction · status · responsible owner · deadlines · pending approvals.
- **28.2 Document Workspace:** original/derived view · page-level citations · redline · clause findings · source panel · OCR confidence · injection alerts.
- **28.3 Legal Research Workspace:** issues · search plan · authorities · proposition evidence · counterarguments · verification status.
- **28.4 Approval Centre:** exact artifact · version/hash · action · destination · recipients · risk · supporting evidence · approve/reject · expiry · audit trail.
- **28.5 Audit Viewer:** event timeline · filters · model/tool/policy versions · no unnecessary sensitive content.

---

# 29. Delivery Roadmap (long-term phases)

> The active execution scope is `docs/execution/MVP_ROADMAP.md`. The phases below define the full journey.

- **Phase 0 — Development Foundation:** toolchain, repository, Git strategy, package management, lint/format/type/test, pre-commit, CI, security scanning, ADR framework. Exit: clean repo, deterministic install, locked dependencies, green CI, documented rollback.
- **Phase 1 — Governance and Security Foundation:** approved root `CLAUDE.md`, `AGENTS.md`, Cursor rules, initial Claude settings skeleton, policy documents, L/R schemas, approval schema, workflow router skeleton, audit event schema, negative-test specifications. Exit: no contradictions, root frozen/tagged, schema tests, documented residual permission/hook risks, no external integrations.
- **Phase 2 — Official Legal Source Supply Chain:** source registry, Federal Register API adapter, WA feed adapter, immutable raw store, hash/version lineage, secure parsing, quarantine, publication gate, freshness monitoring. Exit: fixtures, replay/idempotency, malformed-payload tests, source allowlist, TLS/timeout/size limits, no LLM involvement.
- **Phase 3 — Document Ingestion:** upload, malware/type gate, PDF/DOCX extraction, OCR, provenance, matter isolation, injection scanning. Exit: immutable originals, coordinates retained, OCR quality surfaced, malicious files quarantined, missing pages/attachments detected.
- **Phase 4 — Data and Access Platform:** PostgreSQL, migrations, object storage, identity, RBAC/ABAC, RLS, audit store, approval persistence. Exit: isolation tests, access matrix, backup/restore, no cross-matter leakage.
- **Phase 5 — Hybrid Legal Retrieval:** chunk model, metadata filters, lexical retrieval, vector retrieval, merge/rerank, authority/currency validator, evidence packets. Exit: benchmark dataset, recall/precision targets, stale/repealed tests, claim-level evidence.
- **Phase 6 — First Bounded Agent:** provider-neutral model adapter, structured outputs, approved tools only, retrieval fail-closed, no external actions, verifier loop. Exit: unsupported-claim threshold, citation tests, prompt-injection tests, human review, no model-memory legal answers.
- **Phase 7 — Contract Review:** clause extraction, playbook, redline, preferred/fallback/walk-away, cross-clause analysis, risk register. Exit: golden contracts, human comparison, redline preservation, approval workflow.
- **Phase 8 — Legal Research:** issue decomposition, authorities, treatment checking, research memo, counterarguments, source table. Exit: benchmark questions, source accuracy, currency, human legal review.
- **Phase 9 — Action and Approval Workflows:** L2 drafting, approval centre, anti-replay, optional controlled L3/L4, external dispatch adapters. Exit: authenticated approvals, mutation invalidation, replay tests, L5/L6 blocked.
- **Phase 10 — Full Frontend:** secure UI, matter workspace, document viewer, research interface, approval centre, audit viewer.
- **Phase 11 — Production Security and Evals:** threat model, red team, privacy impact assessment, disaster recovery, release gates, incident runbooks.
- **Phase 12 — Deployment:** Docker, staging, production, AU-region infrastructure where required, monitoring, backup, change management.

---

# 30. Standard Task Workflow

For every task:

1. task brief by the planning assistant; 2. new branch/worktree; 3. bounded Codex prompt; 4. Codex implementation and tests; 5. inspect terminal evidence; 6. Cursor manual review without edits; 7. record review findings; 8. Codex fixes only the findings; 9. full test suite; 10. final diff review; 11. commit; 12. release gate if material; 13. merge by the owner.

## 30.1 Branch Naming

```text
phase-0/dev-foundation · phase-1/security-foundation
phase-2/source-registry · feat/approval-schema
fix/approval-replay · test/prompt-injection · docs/adr-policy-engine
```

## 30.2 Commit Standard

```text
feat(policy): add artifact-bound approval schema
test(security): reject expired approval replay
docs(adr): record policy-engine decision
```

---

# 31. Prompt Template for Codex

```text
Task: <short title>

Read first:
- AGENTS.md
- CLAUDE.md
- <relevant ADRs/policies>

Goal:
<one concrete outcome>

In scope:
- ...

Out of scope:
- ...

Files allowed:
- ...

Requirements:
1. ...

Security constraints:
- fail closed
- no new network access
- no generic shell tool
- no model calls unless explicitly approved
- do not weaken L5/L6 controls

Acceptance criteria:
- ...

Commands to run:
- ...

Evidence required:
- changed files
- test output
- lint/type output
- unresolved risks
- rollback instructions

Stop conditions:
- architecture conflict
- missing dependency/specification
- security control cannot be proven
```

---

# 32. Prompt Template for Cursor Review

```text
Review only. Do not edit files.

Read:
- CLAUDE.md
- AGENTS.md
- relevant policy/workflow
- current diff

Check:
1. architecture drift
2. security boundary violations
3. fail-open behaviour
4. missing validation
5. missing negative tests
6. data leakage
7. approval replay
8. cross-matter access
9. unsupported assumptions
10. discrepancy between code and specification

Report:
- severity
- exact file and line
- exploit/failure scenario
- required fix
- required test
```

---

# 33. Claude Code Security Validation Template

```text
Environment: WSL2/Linux
Mode: controlled test repository
No real client data

Validate:
1. managed settings precedence
2. bypass disabled
3. .env blocked through Read and shell
4. network allowlist
5. PreToolUse critical blocking
6. hook absence detection
7. MCP tool names match deployed schema
8. privileged egress blocked
9. L5/L6 attempts blocked
10. audit failure causes fail-closed

Record:
- Claude Code version
- OS
- settings scope
- exact command
- observed result
- expected result
- pass/fail
- residual weakness
```

---

# 34. Current Project Status

**Approved/design-complete:** product mission · non-lawyer boundary · L0–L6 authority model · R0–R4 risk model · retrieval fail-closed · artifact-bound approval concept · matter isolation principle · memory separation · skill quarantine · Codex/Cursor/Claude Code role split · official-source-first approach · hybrid retrieval direction · phased delivery · eval and release-gate requirements.

**Reference material available:** reviewed Root Constitution · engineering reviews · prior prototypes and ZIPs · initial architecture discussions · scheduled monthly monitoring of Australian Legal AI technology/regulatory changes.

**Not yet production-complete:** owner-rebuilt repository from zero · final Git history · actual managed Claude settings · tested hooks · identity provider · approval persistence · source adapters · database · retrieval · AI runtime · frontend · external integrations · production audit · privacy impact assessment · legal review · penetration test · deployment.

Previously generated ZIPs are references/prototypes only unless independently reviewed, reconstructed, and accepted into the new repository.

---

# 35. Immediate Step-by-Step Plan

## Step 0 — Verify Environment

Run and record:

```powershell
git --version
cursor --version
codex --version
uv --version
uv python list
python --version
node --version
npm --version
docker --version
docker compose version
wsl --status
```

Do not create application code yet.

## Step 1 — Create Clean Repository

```powershell
New-Item -ItemType Directory -Force D:\Projects
Set-Location D:\Projects
New-Item -ItemType Directory australian-legal-ai
Set-Location australian-legal-ai
git init
git branch -M main
git status
cursor .
```

Do not copy prior ZIP contents.

## Step 2 — Establish Governance Files

The first commit contains only: `CLAUDE.md` · `AGENTS.md` · this Master Blueprint · `docs/execution/MVP_ROADMAP.md` · `.gitignore` · `docs/adr/README.md` · archived superseded governance if needed. No FastAPI, Next.js, database, agent, or network integration yet. (The root `README.md` is a Sprint 0 deliverable produced by Codex.)

## Step 3 — Freeze Constitution

Place the reviewed constitution at repository root as `CLAUDE.md`; archive previous versions; run the contradiction checklist; commit; tag `governance-v1.0.0`.

## Step 4 — Codex Sprint 0 Task

Engineering foundation only: package management, lint/format/type/test, pre-commit, CI. No application features, no external services, no model calls. (Full task text: `docs/execution/MVP_ROADMAP.md` §13.)

## Step 5 — Cursor Review

Review dependency choices, scripts, CI, secrets risk, Windows/WSL portability, unnecessary frameworks.

## Step 6 — Accept Sprint 0

Only after: deterministic install · all checks green · clean diff · documented rollback · no Critical/High issues.

---

# 36. Sprint 0 Acceptance Criteria

Git main exists · branch protection plan documented · Python version pinned · package manager selected · dependencies locked · reproducible formatting · linting enabled · static typing enabled · unit-test runner configured · coverage command exists · pre-commit configured · CI runs the same commands · secret scanning enabled · no secrets committed · no application code · no external network integration · ADRs for major tool choices · README contains setup commands · clean clone/install/test verified.

---

# 37. Decision Register

| Decision | Current choice | Status |
|---|---|---|
| Primary implementation agent | Codex | Approved |
| Daily IDE/review | Cursor + Claude | Approved |
| Claude runtime testing | Claude Code on WSL2/Linux | Approved |
| Backend language | Python | Approved |
| Backend framework | FastAPI, when a phase requires it | Provisional |
| Frontend | Next.js + TypeScript | Provisional |
| Database | PostgreSQL | Approved direction |
| Vector store MVP | pgvector (eval-gated) | Provisional |
| Policy MVP | typed in-app engine | Approved |
| External policy service | OPA/Cedar later, if justified | Deferred |
| Workflow framework | explicit state machine first | Approved |
| Agent framework | selected only after the bounded phase | Deferred |
| Legal source approach | official sources, immutable/versioned | Approved |
| Model memory as law | Prohibited | Approved |
| Self-promoting skills | Prohibited | Approved |
| L5/L6 autonomous execution | Prohibited | Approved |
| Product purpose (current) | Portfolio-quality internal prototype | Approved (ADR 0001) |

---

# 38. Open Decisions and Dependencies

To be resolved before production: exact organisational use case · company vs personal scope · authorised roles · lawyer review arrangements · identity provider · hosting provider · Australian data-region requirement · retention periods · legal-source citator provider · email/calendar/DMS integrations · model providers and contracts · budget ceilings · incident owner · insurance and professional-risk considerations · privacy impact assessment · penetration testing plan · source licensing and reuse review.

---

# 39. Legal and Regulatory Baseline

The system must remain compatible with, at minimum: Federal Court GPN-AI and forum-specific practice notes · OAIC Privacy Act and AI guidance · Australian Privacy Principles · Legal Practice Board of WA AI guidance · applicable professional obligations · Commonwealth legislation · WA legislation · court and tribunal procedural rules · privilege, evidence, and confidentiality duties · contractual confidentiality and engagement terms.

Every forum may impose different disclosure and AI-use rules. Blanket footers or blanket disclosure rules are prohibited; disclosure is assessed per forum.

---

# 40. Source References

1. OpenAI Codex: https://openai.com/codex/ · https://openai.com/business/solutions/engineering/ · https://openai.com/index/harness-engineering/
2. Cursor rules and CLI: https://docs.cursor.com/context/rules-for-ai · https://docs.cursor.com/en/cli/using
3. Anthropic Claude Code: https://docs.anthropic.com/en/docs/claude-code/getting-started · https://docs.anthropic.com/en/docs/claude-code/cli-usage
4. Federal Court of Australia GPN-AI: https://www.fedcourt.gov.au/law-and-practice/practice-documents/practice-notes/gpn-ai
5. OAIC guidance: https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/guidance-on-privacy-and-the-use-of-commercially-available-ai-products
6. Legal Practice Board of WA: https://www.lpbwa.org.au/artificial-intelligence-joint-statement
7. Federal Register of Legislation API: https://www.legislation.gov.au/help-and-resources/using-the-legislation-register/data-share-and-reuse
8. WA Legislation notification feeds: https://www.legislation.wa.gov.au/legislation/statutes.nsf/feeds.html

---

# 41. Final Operating Rule

From this date forward:

> Every feature passes through: **requirement → policy → workflow → schema → test → implementation → review → release gate**.

No significant architectural decision lives only in chat; decisions are recorded here or in ADRs.

No agent is turned loose on the repository without a bounded task and acceptance criteria.

No legal answer is reliable without a verified source and pinpoint.

No change enters `main` without tests, diff, evidence, and rollback.

---

**End of Master Blueprint — Version 1.1.0 (English edition)**

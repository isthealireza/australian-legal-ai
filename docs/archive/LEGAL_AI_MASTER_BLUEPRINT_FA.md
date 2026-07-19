# Australian Legal AI OS
## Master Architecture, Governance, Engineering Roadmap and Step-by-Step Delivery Plan

**Document language:** Persian with necessary English technical terms  
**Document status:** Master Project Blueprint  
**Version:** 1.0.0  
**Date:** 20 July 2026  
**Primary jurisdictional focus:** Australia, with initial implementation priority for Commonwealth and Western Australia  
**Repository role:** This document is the project-level source of truth for architecture, delivery sequence, tooling responsibilities, security boundaries, release gates and unresolved dependencies.

---

# 1. Executive Summary

این پروژه قرار نیست یک chatbot عمومی باشد که از حافظه مدل درباره قانون پاسخ بدهد. محصول هدف یک **Private Australian Legal Operations Copilot** است که برای کارهای حقوقی و تجاری سازمانی طراحی می‌شود و می‌تواند:

- پرونده و matter ایجاد و مدیریت کند؛
- jurisdiction و forum را تشخیص دهد؛
- قراردادها و اسناد را تحلیل کند؛
- legal research انجام دهد؛
- legislation، delegated legislation، cases، court rules، practice notes و regulator guidance را بازیابی و نسخه‌بندی کند؛
- claimها، disputeها، noticeها و deadlineها را مدیریت کند؛
- draft، redline، chronology، risk register، legal memorandum و negotiation pack تولید کند؛
- evidence و provenance را حفظ کند؛
- approvalهای دقیق و ضد replay داشته باشد؛
- تا حد مجاز، workflow را پیش ببرد؛
- ولی هرگز خودش را وکیل معرفی نکند و هیچ اقدام الزام‌آور، filing، service، signature، settlement، waiver یا disclosure حساس را خودمختار انجام ندهد.

اصل بنیادین:

> **مدل زبانی منبع قانون نیست. مدل فقط روی evidence packet تأییدشده، policyهای جاری و ابزارهای محدود تحلیل انجام می‌دهد.**

هدف درست «بلد بودن تمام قانون» نیست. هدف درست این است که سیستم:

1. منابع رسمی و جاری را پیدا کند؛
2. jurisdiction، effective date، amendment، commencement، repeal و transition را بررسی کند؛
3. هر proposition حقوقی را به source و pinpoint متصل کند؛
4. در صورت شکست retrieval یا verification متوقف شود؛
5. uncertainty را پنهان نکند؛
6. با شدت متناسب با ریسک، human review و verifier مستقل فعال کند.

---

# 2. Product Mission

سیستم برای این حوزه‌ها طراحی می‌شود:

- Contract review and redlining
- Contract drafting
- Commercial legal research
- Contractual claims
- Dispute and pre-litigation preparation
- Notice preparation
- Settlement preparation
- Evidence and document analysis
- Chronology generation
- Obligation and deadline tracking
- Legal and commercial risk management
- Matter management
- Regulatory and court-facing preparation
- Internal legal operations
- Policy and playbook management
- Knowledge and precedent management
- Audit, approval and governance

## 2.1 Non-goals

سیستم در نسخه‌های موردنظر:

- law firm نیست؛
- admitted lawyer نیست؛
- جایگزین advice و review انسان واجد صلاحیت نمی‌شود؛
- از model memory به‌عنوان authority استفاده نمی‌کند؛
- بدون منبع verified، finding حقوقی قطعی صادر نمی‌کند؛
- autonomously امضا، file، serve، settle، pay، waive یا bind نمی‌کند؛
- به‌صورت خودکار skill یا policy تولیدشده را وارد production نمی‌کند؛
- unrestricted shell، unrestricted network یا unrestricted filesystem tool ندارد؛
- اطلاعات privileged یا sensitive را به provider تأییدنشده ارسال نمی‌کند.

---

# 3. Operating Model: نقش انسان و ابزارها

## 3.1 نقش مالک پروژه

مالک repository و تصمیم نهایی، کاربر انسانی است. وظایف او:

- تأیید scope و business requirements؛
- نگهداری repository و branchها؛
- اجرای taskها؛
- مرور diff؛
- تأیید merge؛
- تصمیم درباره provider، budget، data residency و retention؛
- تعیین افراد authorised؛
- دریافت legal advice واقعی در نقاط لازم؛
- تأیید releaseهای production.

## 3.2 نقش ChatGPT در این پروژه

ChatGPT نقش‌های زیر را دارد:

- Software Architect
- Full-Stack Technical Lead
- AI Systems Architect
- Security Reviewer
- Legal AI Governance Adviser
- Task Designer
- Acceptance-Criteria Designer
- Diff and Evidence Reviewer
- Step-by-Step Technical Coach

ChatGPT به‌صورت پیش‌فرض کد پروژه را به‌جای مالک نمی‌نویسد. وظیفه اصلی آن طراحی task، review خروجی، تشخیص ریسک، توضیح مرحله و نگهداری consistency معماری است.

## 3.3 Codex — ابزار اصلی پیاده‌سازی

**Codex ابزار اصلی اجرای تغییرات repository-level است.**

مناسب برای:

- ساخت چند فایل مرتبط؛
- refactor؛
- test generation؛
- اجرای lint، type check و test؛
- تولید diff؛
- ارائه terminal evidence؛
- اجرای task در branch یا worktree جدا؛
- اصلاح review findings؛
- آماده‌سازی تغییر review-ready.

قانون:

> Codex اجراکننده است، نه تصمیم‌گیر معماری.

هر task Codex باید دارای موارد زیر باشد:

- هدف محدود؛
- in-scope و out-of-scope؛
- فایل‌های مجاز؛
- acceptance criteria؛
- test commands؛
- forbidden changes؛
- rollback instructions؛
- evidence requirements.

## 3.4 Cursor با Claude — IDE و بازبین تعاملی

Cursor برای این موارد استفاده می‌شود:

- مرور سریع repository؛
- فهم ارتباط فایل‌ها؛
- سؤال درباره خط یا function مشخص؛
- manual diff review؛
- architecture review؛
- security review؛
- pair programming؛
- اصلاحات بسیار کوچک و فوری؛
- توضیح کد و tests.

Cursor مسئول ساخت خودمختار یک Phase کامل نیست.

## 3.5 Claude Code واقعی — تست runtime مخصوص Claude Code

استفاده از Claude داخل Cursor برابر با Claude Code runtime نیست.

فقط در Claude Code واقعی باید این موارد آزمایش شوند:

- `.claude/settings.json`
- permission modes
- PreToolUse/PostToolUse hooks
- managed settings
- sandbox
- filesystem/network restrictions
- MCP tool names and schemas
- custom agents
- skills
- `bypassPermissions` posture
- hook failure behaviour

محیط ترجیحی برای این تست:

- WSL2/Linux؛ یا
- Linux container/VM؛
- نه اتکای صرف به native Windows برای security boundary.

## 3.6 Workflow رسمی ابزارها

| فعالیت | ابزار اصلی |
|---|---|
| معماری و task design | ChatGPT + مالک پروژه |
| پیاده‌سازی repository | Codex |
| تست و evidence | Codex |
| manual diff review | Cursor + مالک |
| adversarial review | Cursor/Claude یا Codex task مستقل |
| رفع review | Codex |
| Claude-specific security test | Claude Code در WSL2/Linux |
| merge approval | مالک پروژه |
| legal approval | انسان/وکیل واجد صلاحیت |

دو Agent نباید هم‌زمان روی branch و فایل‌های مشترک write access داشته باشند.

---

# 4. Root Operating Constitution

فایل اصلی governance باید دقیقاً در root پروژه با نام زیر قرار بگیرد:

```text
CLAUDE.md
```

فایل‌هایی مانند موارد زیر root constitution محسوب نمی‌شوند:

```text
CLAUDE.reviewed.md
CLAUDE_v3.md
CLAUDE-final-copy.md
```

نسخه‌های قبلی فقط در archive نگهداری شوند:

```text
docs/archive/governance/
```

## 4.1 اصل سه‌گانه

```text
Capability ≠ Authority ≠ Risk
```

- **Capability:** سیستم از نظر فنی چه کاری می‌تواند انجام دهد؟
- **Authority:** اجازه دارد چه کاری را اجرا کند؟
- **Risk:** artifact یا matter چقدر حساس است؟

هیچ‌کدام جای دیگری را نمی‌گیرد.

## 4.2 اصل Grounding

```text
No grounding, no finding.
No verified source, no legal proposition.
```

## 4.3 اصل Determinism

این کارها باید با ابزار deterministic انجام شوند:

- hashing
- parsing
- diffing
- arithmetic
- deadline calculations
- schema validation
- file type detection
- source-version comparison
- approval comparison
- recipient matching
- document version matching

Judgment و interpretation محدود، با Agent انجام می‌شود.

## 4.4 اصل Fail-Closed

اگر یکی از کنترل‌های لازم موجود نباشد، اقدام حساس متوقف می‌شود:

- retrieval
- source verification
- approval authentication
- audit sink
- verifier
- policy service
- evidence hash
- privacy classification
- endpoint validation
- hook/permission control
- MCP schema validation

---

# 5. Action Authority: L0 تا L6

| Level | تعریف | اجرای AI |
|---|---|---|
| L0 | Read-only research | خودکار، logged |
| L1 | Internal reversible action | خودکار، logged |
| L2 | Draft creation | مجاز فقط در review location و با DRAFT status |
| L3 | Routine external dispatch under standing authority | پیش‌فرض غیرفعال؛ فقط با delegation رسمی و کنترل فنی |
| L4 | Case-specific external dispatch | فقط با approval دقیق، authenticated و artifact-bound؛ در غیر این صورت human dispatch |
| L5 | Legally/financially binding action | فقط تصمیم و اجرای انسان |
| L6 | Filing, service, signature, court/regulator representation, evidence destruction/alteration, privileged disclosure | هرگز autonomously executable نیست |

## 5.1 Anti-decomposition rule

یک action پرریسک را نمی‌توان به چند action کم‌ریسک تقسیم کرد تا classification پایین‌تری بگیرد.

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

# 6. Risk Classification: R0 تا R4

| Risk | تعریف |
|---|---|
| R0 | Administrative/routine |
| R1 | Low risk |
| R2 | Material legal or commercial matter |
| R3 | High legal/commercial/reputational risk |
| R4 | Court, regulator, evidence, privilege, sensitive data or rights-critical |

ریسک در intake تعیین می‌شود و با تغییر scope دوباره بررسی می‌شود.

مثال:

```text
Draft affidavit = L2 / R4
File affidavit  = L6 / R4
```

---

# 7. Verification Depth

## R0–R1

- یک Agent محدود؛
- source verification برای هر legal proposition؛
- grounding check؛
- no external effect.

## R2

- deterministic checks؛
- source/currency check؛
- citation existence and pinpoint check؛
- human review قبل از operational reliance.

## R3

- تمام R2؛
- independent fresh-context verifier؛
- drafter حق final self-certification ندارد؛
- human review.

## R4

- تمام R3؛
- adversarial/red-team review؛
- qualified human or admitted practitioner review؛
- forum-specific disclosure and procedural checks.

نکته:

> Citation existence می‌تواند deterministic بررسی شود، ولی اینکه citation واقعاً proposition حقوقی را پشتیبانی می‌کند یک مسئله interpretation است و کاملاً deterministic نیست.

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

## 8.1 Architectural principle

Workflow-first، policy-enforced، retrieval-grounded و bounded agents.

نه:

```text
One autonomous agent + shell + browser + email + memory
```

## 8.2 Initial stack

### Backend

- Python 3.13
- FastAPI
- Pydantic
- PostgreSQL
- SQLAlchemy or equivalent typed data layer
- Alembic migrations

### Frontend

- Node.js LTS
- Next.js
- TypeScript
- accessible component system
- secure server-side session handling

### Retrieval

MVP:

- PostgreSQL full-text/BM25-compatible lexical approach where adequate
- pgvector
- metadata filtering
- reranking service

Scale-up:

- OpenSearch/Elasticsearch for advanced hybrid retrieval, only when justified.

### Workflow

Initial:

- explicit application state machine؛
- minimal orchestration؛
- no premature framework.

When durable pause/resume and long-running workflows are proven necessary:

- LangGraph or equivalent bounded agent graph.

Enterprise durable outer workflow when genuinely required:

- Temporal.

Do not adopt LangGraph and Temporal simultaneously in the first implementation.

### Policy

MVP:

- typed policy engine inside backend؛
- deny by default؛
- comprehensive tests.

Later:

- OPA or Cedar when multiple independent policy-enforcement points justify a separate policy decision service.

### Storage

- PostgreSQL: structured metadata, matters, users, approvals, policies
- S3-compatible object storage: original and derived documents
- append-only/tamper-evident audit store
- secrets manager
- KMS-managed encryption
- matter-specific access boundaries

### Observability

- OpenTelemetry
- metrics
- security events
- privacy-safe traces
- incident alerts

---

# 9. Repository Architecture

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
│
├── .cursor/
│   ├── rules/
│   └── commands/
│
├── .claude/
│   ├── settings.json
│   ├── hooks/
│   ├── agents/
│   ├── rules/
│   └── skills/
│
├── apps/
│   ├── api/
│   ├── web/
│   └── workers/
│
├── packages/
│   ├── contracts/
│   ├── policy/
│   ├── observability/
│   └── ui/
│
├── workflows/
│   ├── router.yaml
│   ├── matter_intake.md
│   ├── conflict_check.md
│   ├── contract_review.md
│   ├── legal_research.md
│   ├── final_verification.md
│   └── court_facing_review.md
│
├── policies/
│   ├── approval.md
│   ├── ai_disclosure.md
│   ├── change_control.md
│   ├── confidentiality_privilege.md
│   ├── conflicts.md
│   ├── data_classification.md
│   ├── delegation_of_authority.md
│   ├── incident_response.md
│   ├── injection_defence.md
│   ├── model_governance.md
│   ├── playbook.md
│   ├── privacy.md
│   ├── risk_classification.md
│   ├── retention.md
│   └── source_integrity.md
│
├── sources/
│   └── au/
│       ├── registry/
│       ├── commonwealth/
│       ├── wa/
│       ├── courts/
│       └── regulators/
│
├── schemas/
│   ├── approval-record.schema.json
│   ├── legal-source.schema.json
│   ├── matter.schema.json
│   ├── finding.schema.json
│   └── audit-event.schema.json
│
├── tools/
│   ├── hashing/
│   ├── document/
│   ├── deadline/
│   ├── citation/
│   └── approval/
│
├── evals/
│   ├── golden/
│   ├── adversarial/
│   ├── regression/
│   ├── graders/
│   ├── datasets/
│   └── release-gates/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── e2e/
│
├── docs/
│   ├── adr/
│   ├── architecture/
│   ├── threat-model/
│   ├── runbooks/
│   └── archive/
│
├── matters/
│   └── README.md
│
├── logs/
│   └── audit/
│
└── proposals/
    └── workflow-amendments/
```

این structure هدف نهایی است؛ همه پوشه‌ها نباید در اولین commit بدون نیاز ساخته شوند.

---

# 10. Matter Model

هر matter حداقل شامل:

- `matter_id`
- title
- matter type
- jurisdiction
- governing law
- forum
- procedural posture
- parties
- related entities
- capacities
- conflict-check status
- risk class
- deadline flags
- privilege status
- data classification
- responsible human
- authorised reviewers
- source snapshot/version
- open issues
- approvals
- audit references
- retention/hold status

## 10.1 Matter isolation

- cross-matter retrieval ممنوع مگر policy صریح؛
- PostgreSQL Row-Level Security؛
- object-storage prefix isolation؛
- matter-scoped encryption context where possible؛
- traces و eval data بدون privileged matter content؛
- memory فقط matter-scoped.

---

# 11. Matter Intake Workflow

پیش از substantive processing:

1. ایجاد matter ID؛
2. شناسایی parties و capacities؛
3. jurisdiction و governing law؛
4. forum و procedural posture؛
5. Commonwealth/State/Territory analysis؛
6. cross-border elements؛
7. conflict and restricted-matter screening؛
8. privilege/confidentiality/privacy classification؛
9. deadline and limitation flags؛
10. evidence and preservation flags؛
11. insurance notification consideration؛
12. dispute-resolution prerequisites؛
13. preliminary L/R classification؛
14. responsible human assignment.

## 11.1 Emergency deadline mode

اگر limitation، appeal، filing، service یا contractual notice deadline ممکن است نزدیک باشد:

- منتظر intake کامل نمان؛
- فوراً authorised human را alert کن؛
- deadline را provisional علامت بزن؛
- trigger date، timezone و business-day assumptions را ثبت کن؛
- deterministic calculator را اجرا کن؛
- filing-critical date را انسان تأیید کند.

---

# 12. Conflict Check

بررسی:

- current clients
- former clients
- adverse parties
- related entities
- directors/officers
- related matters
- confidential information
- personal interests
- information barriers
- restricted matters

Name match به‌تنهایی conflict نیست.

فرایند:

```text
Candidate match
→ identity resolution
→ relationship analysis
→ information-access analysis
→ human confirmation
→ conflict/consent/barrier decision
```

تصمیم ethical wall، consent یا refusal فقط توسط انسان واجد صلاحیت.

---

# 13. Data Classification

کلاس‌ها:

- PUBLIC
- INTERNAL
- CONFIDENTIAL
- PERSONAL
- SENSITIVE
- PRIVILEGED
- WITHOUT_PREJUDICE
- SUPPRESSED
- STATUTORY_SECRET
- COMPELLED_PRODUCTION
- EVIDENCE_HOLD

## 13.1 Processing rule

قبل از هر external transmission:

- data classification؛
- processor approval؛
- purpose validation؛
- data minimisation؛
- redaction/pseudonymisation where suitable؛
- logging of destination and legal basis.

Local deterministic intake ممکن است حداقل پردازش لازم را انجام دهد:

- malware scan
- hash
- file type detection
- metadata extraction
- local OCR
- preliminary classification
- redaction

---

# 14. Privacy, Privilege and Confidentiality

این مفاهیم جدا هستند:

- privacy
- confidentiality
- client legal privilege
- without-prejudice protection
- suppression
- statutory secrecy
- compelled-production restrictions

Privilege فقط براساس label پذیرفته نمی‌شود. بررسی می‌شود:

- holder
- communication participants
- dominant purpose
- lawyer/client capacity
- confidentiality
- forum
- waiver risk
- attachment and chain context

## 14.1 AI provider due diligence

برای هر provider:

- data retention
- training usage
- data residency
- subcontractors
- administrator access
- encryption
- deletion
- incident notification
- audit rights
- contractual confidentiality
- cross-border disclosure
- model logging
- trace storage

Public AI tools برای personal، sensitive یا privileged information ممنوع هستند مگر policy و legal assessment صریح خلاف آن را تأیید کند.

---

# 15. Legal Source Supply Chain

## 15.1 Source priority

Authority براساس proposition و jurisdiction تعیین می‌شود، نه یک لیست ثابت.

منابع ممکن:

- Constitution
- legislation
- delegated legislation
- commencement instruments
- transitional provisions
- court/tribunal rules
- practice notes
- binding appellate authority
- persuasive authority
- official regulator guidance
- reputable secondary commentary

Regulator guidance و commentary به‌عنوان binding law معرفی نمی‌شوند مگر چارچوب قانونی چنین اثری بدهد.

## 15.2 Initial official sources

Commonwealth:

- Federal Register of Legislation and official API
- Federal Court practice notes
- High Court and relevant federal courts
- official regulator sites

Western Australia:

- WA Legislation
- WA notification feeds
- WA court rules and practice directions
- Legal Practice Board of WA
- WA regulators

## 15.3 Ingestion lifecycle

```text
Official source
→ isolated fetch
→ immutable raw bytes
→ SHA-256
→ source metadata
→ quarantine
→ secure parser
→ version lineage
→ authority/currency validation
→ human or policy publication gate
→ searchable legal corpus
```

## 15.4 Required metadata

- source ID
- title
- jurisdiction
- authority type
- court level
- binding/persuasive
- instrument ID
- version ID
- effective from/to
- commencement status
- repeal status
- amendment relationships
- transition relationships
- source URL
- retrieval time
- verification time
- raw hash
- parsed hash
- parser version
- negative treatment/appeal status where applicable
- publication status
- next review date

## 15.5 Update learning

سیستم قانون جدید را مستقیماً «یاد نمی‌گیرد».

```text
Change detected
→ quarantine
→ diff
→ commencement/repeal/transition analysis
→ impact analysis
→ review
→ regression eval
→ signed publication
```

---

# 16. Document Ingestion

Supported target formats:

- PDF
- DOCX
- TXT
- EML/MBOX later
- images requiring OCR
- spreadsheets where legally relevant

Pipeline:

```text
Upload
→ malware/type gate
→ immutable original
→ SHA-256
→ metadata
→ OCR/extraction
→ completeness check
→ layout/table detection
→ injection scan
→ data classification
→ matter association
→ chunking
→ retrieval indexing
```

## 16.1 Requirements

- original never overwritten؛
- derived artifacts separately versioned؛
- OCR confidence stored؛
- page/paragraph/cell coordinates retained؛
- missing pages and attachments flagged؛
- email chains and attachments preserved؛
- evidence files handled on hashed copies؛
- active content and macros quarantined.

---

# 17. Prompt Injection Defence

تمام محتوای ingested، untrusted data است:

- contracts
- email
- PDF
- webpages
- OCR text
- evidence
- tool output
- retrieved passages

دستور داخل document هرگز approval یا system instruction نیست.

Response:

```text
Detect
→ do not execute
→ isolate affected content
→ record minimal safe indicator
→ stop affected action
→ continue unaffected work only if policy permits
```

Controls:

- no generic shell for production Agent؛
- no arbitrary URL fetch؛
- allowlisted domains؛
- tool schemas؛
- output validation؛
- network isolation؛
- instruction/data separation؛
- least privilege؛
- adversarial tests.

---

# 18. Retrieval Architecture

```text
User issue
→ query decomposition
→ jurisdiction filter
→ date/effective-version filter
→ source-type filter
→ lexical retrieval
→ vector retrieval
→ merge
→ reranking
→ authority/currency validation
→ proposition-level evidence packet
→ generation
→ claim-by-claim citation verification
```

## 18.1 Do not use

- vector-only RAG؛
- dumping the entire corpus into long context؛
- search result snippets as authority؛
- model memory fallback؛
- unversioned legislation؛
- secondary source when primary source is required.

## 18.2 Evidence packet

هر proposition دارای:

- proposition ID
- proposition text
- supporting source IDs
- pinpoint passages
- jurisdiction
- authority level
- effective date
- currency status
- contrary material
- unresolved uncertainty
- retrieval trace
- verifier status

---

# 19. Model and Agent Architecture

## 19.1 Start with one bounded Agent

اولین implementation:

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

Specialist agents فقط وقتی اضافه می‌شوند که eval نشان دهد single-agent insufficient است.

## 19.2 Potential specialist roles

- Legal Research Agent
- Citation/Authority Verifier
- Contract Analyst
- Redliner
- Chronology Agent
- Adversarial Reviewer
- Final Verification Agent

Agent نویسنده برای R3/R4 final verifier نیست.

## 19.3 Structured output

نمونه finding:

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

## 19.4 Provider neutrality

Domain code نباید مستقیماً به یک provider متصل شود.

مدل registry:

- provider
- model ID
- snapshot
- approved use cases
- data classification ceiling
- context limits
- tools allowed
- evaluation version
- approval date
- rollback model

هر model upgrade نیازمند regression eval و release gate است.

---

# 20. Memory and Continuous Learning

چهار نوع memory:

## 20.1 Session memory

- ephemeral
- expires
- not authoritative

## 20.2 Matter memory

- scoped to one matter
- access controlled
- versioned
- cannot cross matters

## 20.3 Organisational knowledge

- approved templates
- clause playbooks
- policies
- approved precedents
- reviewed FAQs

## 20.4 Skill registry

- versioned
- signed/reviewed
- tested
- not self-promoted

Learning pipeline:

```text
Observed issue
→ candidate improvement
→ proposal
→ quarantine
→ security review
→ adversarial eval
→ regression eval
→ authorised maintainer approval
→ signed release
```

Agent اجازه ندارد production skill، workflow، policy یا legal source را مستقیم بازنویسی کند.

---

# 21. Contract Review Workflow

1. intake and matter validation؛
2. identify operative document/version؛
3. hash original؛
4. completeness and annexure check؛
5. jurisdiction/governing law؛
6. clause segmentation؛
7. obligations, dates, amounts and cross-references؛
8. playbook comparison؛
9. legal research only where necessary؛
10. commercial and legal analysis separated؛
11. risk classification؛
12. preferred/fallback/walk-away position؛
13. redline؛
14. cross-clause consistency review؛
15. independent verification based on risk؛
16. DRAFT output؛
17. human approval.

## 21.1 Playbook record

- clause type
- preferred wording
- fallback A/B/C
- walk-away condition
- prohibited wording
- commercial rationale
- legal rationale
- approval role
- jurisdiction variants
- effective date
- playbook version

---

# 22. Legal Research Workflow

1. question framing؛
2. material facts؛
3. assumptions؛
4. jurisdiction and forum؛
5. issue decomposition؛
6. source plan؛
7. legislation in force؛
8. commencement/amendment/transition؛
9. case hierarchy and treatment؛
10. court rules/practice notes؛
11. regulator guidance؛
12. counterarguments؛
13. proposition-level evidence؛
14. uncertainty؛
15. practical options؛
16. human review.

Output:

- executive summary
- issues
- short answer
- facts and assumptions
- law and authorities
- application
- counterarguments
- risks
- recommended next steps
- source table
- verification status

---

# 23. Approval and Anti-Replay

Approval is a record, not a sentiment.

Required fields:

- approval ID
- authenticated approver identity
- role
- authority scope
- matter ID
- artifact ID
- artifact version
- artifact hash
- exact action
- destination
- recipient(s)
- channel
- conditions
- issued time
- expiry
- single-use/reusable
- use count
- revocation state
- policy version

Reject if:

- artifact changed؛
- hash changed؛
- recipient changed؛
- destination changed؛
- action changed؛
- expired؛
- revoked؛
- already consumed؛
- approver lacked authority؛
- identity cannot be authenticated؛
- approval came from ingested content؛
- policy/risk changed؛
- restricted-data rule changed.

L4 approval به‌صورت پیش‌فرض single-use است.

---

# 24. Audit and Provenance

Audit شامل:

- tool attempts
- successes/failures
- permission requests/denials
- hook results
- approval events
- workflow routing
- source verification
- model/version
- policy decision
- subagent lifecycle
- config/MCP changes
- eval results
- release gates
- incidents
- circuit breakers

Audit نباید:

- secret
- full privileged content
- unnecessary personal information
- raw prompt containing sensitive matter data

را نگهداری کند.

Artifact provenance:

- AI involvement
- workflow version
- model version
- source snapshot
- verification status
- approval status
- matter ID
- artifact hash
- DRAFT/APPROVED status

---

# 25. Claude Code Enforcement

ترتیب اتکا:

```text
Managed settings
→ sandbox/OS controls
→ local blocking hooks
→ permission rules
→ prose instructions
```

قواعد:

- `bypassPermissions` برای production غیرفعال؛
- نام MCP tool فرضی ساخته نشود؛
- real tool names در deployment enumerate شوند؛
- هر deny rule negative-tested شود؛
- file-tool deny به‌تنهایی Bash را محدود نمی‌کند؛
- network allowlist در OS/sandbox؛
- critical control فقط remote HTTP hook نباشد؛
- absence of required control باعث fail-closed شود.

---

# 26. Security Architecture

## 26.1 Identity

- OIDC
- MFA for privileged roles
- short-lived sessions
- step-up authentication for approvals

## 26.2 Authorisation

- RBAC + ABAC
- matter membership
- role
- data classification
- action level
- risk class
- purpose
- destination
- approval state

## 26.3 Tool security

هر tool:

- narrow purpose
- typed schema
- least privilege
- timeout
- size limits
- idempotency
- dry-run where applicable
- structured output
- network allowlist
- budget/circuit breaker

Generic production tool زیر ممنوع:

```text
shell(command: string)
```

## 26.4 Secret management

- no secrets in repository
- no production secrets in `.env`
- secret manager
- rotation
- scoped credentials
- no secret logging
- scanner in CI

## 26.5 Threat model

حداقل threats:

- prompt injection
- data exfiltration
- cross-matter leakage
- malicious document
- tool abuse
- approval replay
- stale law
- fake citation
- compromised provider
- poisoned memory
- supply-chain compromise
- insider misuse
- audit tampering
- evidence modification
- insecure logs

---

# 27. Evals and Release Gates

## 27.1 Metrics

- retrieval recall@K
- citation precision
- pinpoint accuracy
- authority correctness
- legal currency
- jurisdiction accuracy
- unsupported claim rate
- deadline accuracy
- injection containment
- policy violation rate
- cross-matter leakage
- human override rate
- latency
- cost
- trace completeness

## 27.2 Adversarial cases

- repealed law
- future amendment not commenced
- transitional provision
- incomplete OCR
- missing annexure
- fake case
- real citation that does not support claim
- negative treatment
- wrong jurisdiction
- prompt injection in contract
- prompt injection in email
- malicious tool output
- same-name parties
- deadline around holiday/weekend
- hash-mismatched approval
- expired approval
- approval replay
- provider timeout
- audit failure
- retrieval failure
- cross-matter access
- privileged text in logs

## 27.3 Release gate

Material changes requiring gate:

- CLAUDE.md
- AGENTS.md
- rules
- skills
- workflows
- agents
- tools
- models
- source parsers
- MCP servers
- hooks
- permissions
- data schemas
- policy engine

Release evidence:

- full test suite
- security tests
- eval results
- diff
- migration plan
- rollback plan
- unresolved risks
- approval owner

---

# 28. Frontend Product Features

## 28.1 Matter Dashboard

- matter list
- risk
- jurisdiction
- status
- responsible owner
- deadlines
- pending approvals

## 28.2 Document Workspace

- original/derived view
- page-level citations
- redline
- clause findings
- source panel
- OCR confidence
- injection alerts

## 28.3 Legal Research Workspace

- issues
- search plan
- authorities
- proposition evidence
- counterarguments
- verification status

## 28.4 Approval Centre

- exact artifact
- version/hash
- action
- destination
- recipients
- risk
- supporting evidence
- approve/reject
- expiry
- audit trail

## 28.5 Audit Viewer

- event timeline
- filters
- model/tool/policy versions
- no unnecessary sensitive content

---

# 29. Delivery Roadmap

## Phase 0 — Development Foundation

Deliverables:

- toolchain verification
- repository
- Git strategy
- Python/Node package management
- lint/format/type/test
- pre-commit
- CI
- security scanning
- ADR framework

Exit criteria:

- clean repository
- deterministic install
- locked dependencies
- test/lint commands
- CI green
- rollback documented

## Phase 1 — Governance and Security Foundation

Deliverables:

- approved root `CLAUDE.md`
- `AGENTS.md`
- Cursor rules
- initial Claude settings skeleton
- policy documents
- L/R schemas
- approval schema
- workflow router skeleton
- audit event schema
- negative-test specifications

Exit criteria:

- no contradictions
- root frozen/tagged
- schema tests
- permission/hook residual risks documented
- no external integrations

## Phase 2 — Official Legal Source Supply Chain

Deliverables:

- source registry
- Federal Register API adapter
- WA feed adapter
- immutable raw store
- hash/version lineage
- secure parsing
- quarantine
- publication gate
- freshness monitoring

Exit criteria:

- fixtures
- replay/idempotency
- malformed payload tests
- source allowlist
- TLS/timeout/size limit
- no LLM involvement

## Phase 3 — Document Ingestion

Deliverables:

- upload
- malware/type gate
- PDF/DOCX extraction
- OCR
- provenance
- matter isolation
- injection scanning

Exit criteria:

- originals immutable
- coordinates retained
- OCR quality surfaced
- malicious files quarantined
- missing pages/attachments detected

## Phase 4 — Data and Access Platform

Deliverables:

- PostgreSQL
- migrations
- object storage
- identity
- RBAC/ABAC
- RLS
- audit store
- approvals persistence

Exit criteria:

- isolation tests
- access matrix
- backup/restore
- no cross-matter leakage

## Phase 5 — Hybrid Legal Retrieval

Deliverables:

- chunk model
- metadata filters
- lexical retrieval
- vector retrieval
- merge/rerank
- authority/currency validator
- evidence packets

Exit criteria:

- benchmark dataset
- recall/precision targets
- stale/repealed tests
- claim-level evidence

## Phase 6 — First Bounded Agent

Deliverables:

- provider-neutral model adapter
- structured outputs
- approved tools only
- retrieval fail-closed
- no external actions
- verifier loop

Exit criteria:

- unsupported claim threshold
- citation tests
- prompt-injection tests
- human review
- no model-memory legal answer

## Phase 7 — Contract Review

Deliverables:

- clause extraction
- playbook
- redline
- preferred/fallback/walk-away
- cross-clause analysis
- risk register

Exit criteria:

- golden contracts
- human comparison
- redline preservation
- approval workflow

## Phase 8 — Legal Research

Deliverables:

- issue decomposition
- authorities
- treatment checking
- research memo
- counterarguments
- source table

Exit criteria:

- benchmark questions
- source accuracy
- currency
- human legal review

## Phase 9 — Action and Approval Workflows

Deliverables:

- L2 drafting
- approval centre
- anti-replay
- optional controlled L3/L4
- external dispatch adapters

Exit criteria:

- authenticated approvals
- mutation invalidation
- replay tests
- L5/L6 blocked

## Phase 10 — Full Frontend

Deliverables:

- secure UI
- matter workspace
- document viewer
- research interface
- approval centre
- audit viewer

## Phase 11 — Production Security and Evals

Deliverables:

- threat model
- red team
- privacy impact assessment
- disaster recovery
- release gates
- incident runbooks

## Phase 12 — Deployment

Deliverables:

- Docker
- staging
- production
- AU-region infrastructure where required
- monitoring
- backup
- change management

---

# 30. Standard Task Workflow

برای هر task:

1. task brief توسط ChatGPT؛
2. branch/worktree جدید؛
3. Codex prompt محدود؛
4. Codex implementation and tests؛
5. inspect terminal evidence؛
6. Cursor manual review بدون edit؛
7. review findings ثبت شود؛
8. Codex فقط findings را اصلاح کند؛
9. full test suite؛
10. final diff review؛
11. commit؛
12. release gate if material؛
13. merge by owner.

## 30.1 Branch naming

```text
phase-0/dev-foundation
phase-1/security-foundation
phase-2/source-registry
feat/approval-schema
fix/approval-replay
test/prompt-injection
docs/adr-policy-engine
```

## 30.2 Commit standard

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
2. ...

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
1. architecture drift;
2. security boundary violations;
3. fail-open behaviour;
4. missing validation;
5. missing negative tests;
6. data leakage;
7. approval replay;
8. cross-matter access;
9. unsupported assumptions;
10. discrepancy between code and specification.

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
1. managed settings precedence;
2. bypass disabled;
3. .env blocked through Read and shell;
4. network allowlist;
5. PreToolUse critical blocking;
6. hook absence detection;
7. MCP tool names match deployed schema;
8. privileged egress blocked;
9. L5/L6 attempts blocked;
10. audit failure causes fail-closed.

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

## Approved/design-complete

- product mission
- non-lawyer boundary
- L0–L6 authority model
- R0–R4 risk model
- retrieval fail-closed
- artifact-bound approval concept
- matter isolation principle
- memory separation
- skill quarantine
- Codex/Cursor/Claude Code role split
- official-source-first approach
- hybrid retrieval direction
- phased delivery
- eval and release-gate requirements

## Reference material available

- reviewed Root Constitution
- Version C engineering review
- prior project prototypes and ZIPs
- initial architecture discussions
- scheduled monthly monitoring for Australian Legal AI technology/regulatory changes

## Not yet treated as production-complete

- repository rebuilt by owner from zero
- final Git history
- actual managed Claude settings
- tested hooks
- identity provider
- approval persistence
- source adapters
- database
- retrieval
- AI runtime
- frontend
- external integrations
- production audit
- privacy impact assessment
- legal review
- penetration test
- deployment

Previous generated ZIPs are references/prototypes only unless independently reviewed, reconstructed and accepted into the new repository.

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
py --version
node --version
npm --version
docker --version
docker compose version
wsl --status
```

Do not create application code yet.

## Step 1 — Create Clean Repository

```powershell
New-Item -ItemType Directory -Force C:\Projects
Set-Location C:\Projects
New-Item -ItemType Directory australian-legal-ai
Set-Location australian-legal-ai
git init
git branch -M main
git status
cursor .
```

Do not copy prior ZIP contents.

## Step 2 — Establish Governance Files

First commit will contain only:

- `CLAUDE.md`
- `AGENTS.md`
- `README.md`
- this Master Blueprint
- `.gitignore`
- `docs/adr/README.md`
- archive of superseded constitution, if needed

No FastAPI، Next.js، database، Agent یا network integration yet.

## Step 3 — Freeze Constitution

Actions:

- rename reviewed constitution to `CLAUDE.md`
- place at repository root
- archive previous versions
- review contradiction checklist
- commit
- create Git tag:

```text
governance-v1.0.0
```

## Step 4 — Codex Phase 0 Task

Codex task:

- create engineering foundation only؛
- package management؛
- lint/format/type/test؛
- pre-commit؛
- CI؛
- no application features؛
- no external services؛
- no model calls.

## Step 5 — Cursor Review

Cursor reviews:

- dependency choices
- scripts
- CI
- secrets risk
- Windows/WSL portability
- unnecessary frameworks

## Step 6 — Accept Phase 0

Only after:

- deterministic install
- all checks green
- clean diff
- rollback documented
- no Critical/High issue.

---

# 36. Phase 0 Acceptance Criteria

- Git main exists
- branch protection plan documented
- Python version pinned
- Node version pinned
- package manager selected
- dependencies locked
- formatting reproducible
- linting enabled
- static typing enabled
- unit-test runner configured
- test coverage command exists
- pre-commit configured
- CI runs same commands
- secret scanning enabled
- no secret committed
- no application code
- no external network integration
- ADR for major tool choices
- README contains setup commands
- clean clone/install/test verified

---

# 37. Decision Register

| Decision | Current choice | Status |
|---|---|---|
| Primary implementation agent | Codex | Approved |
| Daily IDE/review | Cursor + Claude | Approved |
| Claude runtime test | Claude Code in WSL2/Linux | Approved |
| Backend language | Python | Approved |
| Backend framework | FastAPI, when Phase requires it | Provisional-approved |
| Frontend | Next.js + TypeScript | Provisional-approved |
| Database | PostgreSQL | Approved direction |
| Vector store MVP | pgvector | Provisional |
| Policy MVP | typed in-app engine | Approved |
| External policy service | OPA/Cedar later if justified | Deferred |
| Workflow framework | explicit state machine first | Approved |
| Agent framework | selected only after bounded-agent phase | Deferred |
| Legal source approach | official sources, immutable/versioned | Approved |
| Model memory as law | Prohibited | Approved |
| Self-promoting skills | Prohibited | Approved |
| L5/L6 autonomous execution | Prohibited | Approved |

---

# 38. Open Decisions and Dependencies

قبل از production باید تعیین شوند:

- exact organisational use case؛
- company vs personal scope؛
- authorised roles؛
- lawyer review arrangements؛
- identity provider؛
- hosting provider؛
- Australian data-region requirement؛
- retention periods؛
- legal-source citator provider؛
- email/calendar/DMS integrations؛
- model providers and contracts؛
- budget ceilings؛
- incident owner؛
- insurance and professional-risk considerations؛
- privacy impact assessment؛
- penetration testing plan؛
- source licensing and reuse review.

---

# 39. Legal and Regulatory Baseline

سیستم باید حداقل با این دسته منابع سازگار باشد:

- Federal Court GPN-AI and forum-specific practice notes
- OAIC Privacy Act and AI guidance
- Australian Privacy Principles
- Legal Practice Board of WA AI guidance
- applicable professional obligations
- Commonwealth legislation
- WA legislation
- court and tribunal procedural rules
- privilege, evidence and confidentiality duties
- contractual confidentiality and engagement terms

هر forum ممکن است disclosure و AI-use rules متفاوت داشته باشد؛ blanket footer یا blanket disclosure rule ممنوع است.

---

# 40. Source References

1. OpenAI Codex product and engineering guidance:
   - https://openai.com/codex/
   - https://openai.com/business/solutions/engineering/
   - https://openai.com/index/harness-engineering/

2. Cursor official rules and CLI guidance:
   - https://docs.cursor.com/context/rules-for-ai
   - https://docs.cursor.com/en/cli/using

3. Anthropic Claude Code official setup and CLI:
   - https://docs.anthropic.com/en/docs/claude-code/getting-started
   - https://docs.anthropic.com/en/docs/claude-code/cli-usage

4. Federal Court of Australia GPN-AI:
   - https://www.fedcourt.gov.au/law-and-practice/practice-documents/practice-notes/gpn-ai

5. OAIC guidance:
   - https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/guidance-on-privacy-and-the-use-of-commercially-available-ai-products

6. Legal Practice Board of Western Australia:
   - https://www.lpbwa.org.au/artificial-intelligence-joint-statement

7. Federal Register of Legislation API:
   - https://www.legislation.gov.au/help-and-resources/using-the-legislation-register/data-share-and-reuse

8. Western Australian Legislation notification feeds:
   - https://www.legislation.wa.gov.au/legislation/statutes.nsf/feeds.html

---

# 41. Final Operating Rule

از این تاریخ به بعد:

> هر feature باید از مسیر **requirement → policy → workflow → schema → test → implementation → review → release gate** عبور کند.

هیچ تصمیم معماری مهمی فقط در chat باقی نمی‌ماند. تصمیم‌ها در این سند یا در ADR ثبت می‌شوند.

هیچ Agentی بدون task محدود و acceptance criteria روی repository رها نمی‌شود.

هیچ پاسخ حقوقی بدون verified source و pinpoint قابل اتکا نیست.

هیچ change جدیدی بدون tests، diff، evidence و rollback وارد `main` نمی‌شود.

---

**End of Master Blueprint — Version 1.0.0**

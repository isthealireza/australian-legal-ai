# ADR 0015: Phase 5 Slice 1 — Grounded Drafting with Mock Model

- Status: Accepted
- Date: 2026-08-17
- Accepted: 2026-08-17 (owner-approved)

## Context

Phase 4 (ADRs 0013–0014) delivers a deterministic, read-only research pipeline
over recorded WA legislation fixtures. Phase 4 Slice 2 adds section body-text
records for ss 55–56 of the Road Traffic Act 1974 (WA); both sections carry
`"verified": false` and may not be used in any drafting path until independent
human verification is performed.

`MVP_ROADMAP.md §5` pre-specifies a provider-neutral model interface:

```python
class LegalAnswerModel(Protocol):
    async def answer(self, request: GroundedAnswerRequest) -> GroundedAnswer: ...
```

`CASEWORK_OS_ROADMAP.md §Phase 5` requires: deterministic prompt/input builder;
strict structured output; mock adapter; draft versioning and provenance; output
validation; prompt-injection tests; no unrestricted tools on the product model;
no live network to providers in this phase.

`PROJECT_GOVERNANCE.md §3` classifies draft creation as L2 ("Only in review
locations, marked DRAFT"). `§7` requires no unrestricted tool access for the
product model. `§2.4` requires fail-closed behaviour on any missing control.

ADR 0014 §Consequences preserved a critical design constraint:

> "Converting `EvidenceItem` to a dataclass would silently downgrade the
> `Literal[True]` enforcement in Phase 5; this note is preserved from ADR 0013."

This ADR adopts a different approach: `EvidenceItem` with `Literal[True]` as the
untrusted request boundary is **not** used. Using `Literal[True]` at the untrusted
boundary would prevent `DraftingService` from producing an audited typed refusal
for unverified evidence — a caller supplying `verified=False` would receive
`ValidationError` rather than `DraftingRefused(EVIDENCE_NOT_VERIFIED)`. Instead,
Phase 5 Slice 1 follows the Phase 4 trust model: `RecordedSection.verified`
remains `bool`; the service gate checks `section.verified is not True` and
produces a proper audited `DraftingRefused` event.

Phase 5 Slice 1 binds its evidence directly to the existing Phase 4 contracts
(`WaEvidencePacket`, `RecordedWaSource`, `RecordedSection`) rather than
introducing a freestanding `EvidenceItem` whose source identity, provision, text,
and verification flag can all be independently invented by the caller.

## Decision

### 1. Scope

Phase 5 Slice 1 adds exactly:

- `src/legal_ai/drafting/` — a new package (six source files; no `errors.py`)
- `tests/drafting/` — a new test directory (six test files)
- `tests/support/drafting_audit.py` — in-memory audit test doubles
- `tests/support/drafting_adapter.py` — mock, spy, and failing adapter test doubles
- `docs/adr/0015-...md` — this document

Authority level: **L2 only** (`PROJECT_GOVERNANCE.md §3`: draft creation; "Only
in review locations, marked DRAFT"). No L3+ capability is introduced.

The first model call in this project occurs in this slice, via `MockDraftingAdapter`
only. The adapter has no network access, no I/O beyond its own call-count counter,
and lives in `tests/support/`, not `src/`. No production adapter implementation
is added in Slice 1. No production drafting wiring exists in Slice 1.

Phase 5 Slice 1 does **not** add:

- any live model provider (no Anthropic, OpenAI, Google, or other adapter)
- any network call or HTTP client use
- any new Python runtime dependency (no LLM SDK)
- any Alembic migration
- any database table, row, or write of any kind
- any Evidence Vault write
- any `source_document_captures` write
- any playbook activation
- any external action (email, court filing, submission, signature)
- any API (FastAPI, REST, GraphQL, WebSocket)
- any UI or browser interface
- any approval workflow or draft-to-approved transition
- any durable draft storage
- any modification to `src/legal_ai/research/` (any file)
- any modification to `src/legal_ai/playbooks/grounding.py`
- any modification to `FailClosedGroundingGate` (untouched; remains refuse-closed)
- any modification to `service.py`, `validation.py`, `audit.py`, or `types.py`
  in `src/legal_ai/research/`
- any change to the real WA fixture (`verified` flags remain `false`)
- any L3+ authority
- any `EvidenceItem` class with `verified: Literal[True]` as the untrusted
  request boundary (this design is rejected — see Context)

### 2. Input Contract

#### 2.1 WaDraftingCandidate

`WaDraftingCandidate` is a frozen dataclass that pairs one validated Phase 4
packet with the corpus source record needed to resolve the section body text.
Both fields are accepted as provided by the caller. **No field is trusted until
`DraftingService.draft()` has verified all structural consistency checks and
section integrity checks in the gate.**

```python
@dataclass(frozen=True, slots=True)
class WaDraftingCandidate:
    """One WA evidence candidate. Both fields are untrusted until the service gate passes."""

    packet: WaEvidencePacket    # validated Phase 4 packet
    source: RecordedWaSource    # corpus record; untrusted until gate verifies consistency
```

`WaEvidencePacket` (from `legal_ai.research.models`) is already a fully
validated Phase 4 contract: it was produced only after deterministic validation
and a recorded audit event (`audit_result: Literal[ResearchAuditResult.RECORDED]`).
Its fields are structurally correct. However, `RecordedWaSource` is untrusted
recorded data — the caller is responsible for supplying it. The service gate
verifies structural consistency between `packet` and `source` before admitting
any section.

#### 2.2 WaDraftingRequest

```python
class WaDraftingRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        arbitrary_types_allowed=True,   # required for WaDraftingCandidate in tuple
    )

    matter_id: UUID
    purpose: Annotated[
        str,
        StringConstraints(strict=True, min_length=1, max_length=1_000),
    ]
    candidates: tuple[WaDraftingCandidate, ...]  # may be empty; gate enforces non-empty
```

`purpose` is validated at construction by Pydantic (non-empty, ≤ 1 000 chars).
An empty `candidates` tuple is accepted at construction; the service gate refuses
it with `EVIDENCE_EMPTY`. This allows the service — not Pydantic — to produce
the audited typed refusal.

### 3. Verification Gate

The verification gate is a fixed sequence of checks inside `DraftingService.draft()`
that runs **before** any adapter call. The gate logic is co-located with the
service to prevent it from being bypassed by wiring. The first failing check
returns immediately; no partial result is produced.

The gate proceeds in two phases: per-candidate checks (for each candidate in
order), then cross-candidate checks. Cross-candidate checks run only after all
per-candidate checks pass.

**Typed refusal codes:**

```python
class DraftingRefusalCode(StrEnum):
    EVIDENCE_EMPTY = "EVIDENCE_EMPTY"
    EVIDENCE_NOT_VERIFIED = "EVIDENCE_NOT_VERIFIED"
    EVIDENCE_HASH_MISMATCH = "EVIDENCE_HASH_MISMATCH"
    EVIDENCE_SOURCE_MISMATCH = "EVIDENCE_SOURCE_MISMATCH"
    EVIDENCE_PROVISION_MISMATCH = "EVIDENCE_PROVISION_MISMATCH"
    EVIDENCE_DUPLICATE_PROVISION = "EVIDENCE_DUPLICATE_PROVISION"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
```

**Terminal codes:**

```python
class DraftingTerminalCode(StrEnum):
    AUDIT_SINK_UNAVAILABLE = "AUDIT_SINK_UNAVAILABLE"
    ADAPTER_FAILURE = "ADAPTER_FAILURE"
```

**Typed result union:**

```python
DraftingResult = DraftResult | DraftingRefused | DraftingTerminated
```

**Gate steps (mandatory; must not be reordered):**

**Step 1 — Audit sink present:**
If `audit_sink is None` → return `DraftingTerminated(AUDIT_SINK_UNAVAILABLE)`.
No further work.

**Step 2 — Candidates non-empty:**
If `len(request.candidates) == 0` → proceed to C (refusal audit), return
`DraftingRefused(EVIDENCE_EMPTY)`.

**Step 3 — Per-candidate: source structural consistency:**
For each candidate, verify all of the following. Any failure → `EVIDENCE_SOURCE_MISMATCH`:

- `source.source_id == packet.source_id` — source identity matches packet
- `source.sha256 == packet.sha256` — recorded SHA-256 matches packet;
  `RecordedWaSource.sha256` is `str | None`; a `None` value always fails
- `sha256(source.source_content).hexdigest() == packet.sha256` — computed hash
  of the provided source content matches the packet's recorded hash
- `source.source_system == packet.source_system` — must be exactly equal;
  `RecordedWaSource.source_system` is `str | None`; a `None` value fails
- `source.jurisdiction == packet.jurisdiction` — must be exactly equal;
  `RecordedWaSource.jurisdiction` is `str | None`; a `None` value fails

**Structural consistency disclaimer (mandatory — must not be weakened):**

> These checks establish structural consistency only. They verify that the
> provided `RecordedWaSource` and `WaEvidencePacket` carry mutually consistent
> identifiers and that the source content computes the same hash as the packet
> records. They do **not** make the caller-provided pair cryptographically
> authentic, and they do not prove that the `RecordedWaSource` originated from
> the authorised research workflow rather than being constructed to match the
> packet.
>
> Because Slice 1 has no production drafting wiring and all successful tests use
> synthetic fixtures, this residual risk is accepted for Slice 1 only. A future
> production/live-model slice must establish trusted wiring from the authorised
> research path and must not rely on caller-constructed internally consistent
> objects.

**Step 4 — Per-candidate: section lookup:**
Find the `RecordedSection` where `section.identifier == packet.provision_identifier`
within `source.sections`. If no such section exists → `EVIDENCE_PROVISION_MISMATCH`.

**Step 5 — Per-candidate: verification identity check:**
If `section.verified is not True` → `EVIDENCE_NOT_VERIFIED`.
This is a Python identity check (`is not True`), not an equality check.
Values not equal to the Python `True` singleton — including `False`, `1`,
`"true"`, `None`, or any other truthy value — do not satisfy this check.
`RecordedSection` is a frozen dataclass; Python does not enforce type annotations
at runtime. `RecordedSection(verified=1)` succeeds at construction. The service
gate is the enforcing boundary.

**Step 6 — Per-candidate: section text hash integrity:**
If `sha256(section.text.encode("utf-8")).hexdigest() != section.text_sha256` →
`EVIDENCE_HASH_MISMATCH`. Hash integrity proves only that the text is byte-for-byte
the text as recorded at fixture time. It does not constitute verification (§11).

**Step 7 — Cross-candidate: duplicate provision:**
If any two candidates share the same `provision_identifier` and the same section
text → `EVIDENCE_DUPLICATE_PROVISION`.

**Step 8 — Cross-candidate: conflicting evidence:**
If any two candidates share the same `provision_identifier` but provide different
section texts → `EVIDENCE_CONFLICT`.

Only after all eight steps pass does the service construct `VerifiedDraftingInput`
(§4) and call the adapter. Sequencing of audit recording for each outcome is
specified in §9.

### 4. Internal Post-Gate Representation

`VerifiedDraftingInput` and `_VerifiedSection` are **internal** to the drafting
package. Neither is exported from `src/legal_ai/drafting/__init__.py`. Neither
is a supported application entry point. `DraftingService` is the supported
boundary; `DraftingAdapter.draft()` is an internal dependency, not a public
contract.

Only after all eight gate steps pass does the service construct these types:

```python
@dataclass(frozen=True, slots=True)
class _VerifiedSection:
    """Internal. Constructed by DraftingService only, after all gate steps pass."""

    source_id: str
    provision_identifier: str
    pinpoint: str
    statutory_text: str         # section.text from the verified RecordedSection
    text_sha256: str            # section.text_sha256 from the verified RecordedSection
    heading: str | None         # section.heading; may be None


@dataclass(frozen=True, slots=True)
class VerifiedDraftingInput:
    """Internal. Produced exclusively by DraftingService after all gate steps pass.
    DraftingAdapter.draft() receives only this type."""

    matter_id: UUID
    purpose: str
    sections: tuple[_VerifiedSection, ...]
```

`_VerifiedSection` is private (underscore prefix). `VerifiedDraftingInput` is
importable from `legal_ai.drafting.models` directly (for use in
`tests/support/drafting_adapter.py`), but is **not** exported from the package
root. No public helper may invoke `DraftingAdapter.draft()` directly.

### 5. Mock Model Boundary

#### 5.1 DraftingAdapter Protocol (production code)

`src/legal_ai/drafting/adapters.py` defines the Protocol only. No adapter
implementation lives in `src/`. `DraftingAdapter` is **not** exported from
`src/legal_ai/drafting/__init__.py`.

```python
@runtime_checkable
class DraftingAdapter(Protocol):
    @property
    def adapter_id(self) -> str: ...

    def draft(self, input: VerifiedDraftingInput) -> str: ...
```

`DraftingAdapter` is importable from `legal_ai.drafting.adapters` directly
(for `DraftingService` and test support files), but is not part of the public
package API surface.

#### 5.2 Test doubles (test support code)

`tests/support/drafting_adapter.py` provides all adapter test doubles.
These must not be imported from any `src/` module.

```python
class MockDraftingAdapter:
    """Deterministic local adapter. No network. No I/O. Call count is observable."""

    _ADAPTER_ID = "mock_v1"

    def __init__(self, *, response: str | None = None) -> None:
        self._call_count = 0
        self._response = response

    @property
    def adapter_id(self) -> str:
        return self._ADAPTER_ID

    @property
    def call_count(self) -> int:
        return self._call_count

    def draft(self, input: VerifiedDraftingInput) -> str:
        self._call_count += 1
        if self._response is not None:
            return self._response
        lines = [f"[DRAFT] Purpose: {input.purpose}"]
        for section in input.sections:
            lines.append(
                f"\n{section.provision_identifier} ({section.pinpoint}):\n"
                f"{section.statutory_text}"
            )
        return "\n".join(lines)


class SpyDraftingAdapter:
    """Records every VerifiedDraftingInput for assertion. No side effects."""

    _ADAPTER_ID = "spy_v1"

    def __init__(self) -> None:
        self._inputs: list[VerifiedDraftingInput] = []

    @property
    def adapter_id(self) -> str:
        return self._ADAPTER_ID

    @property
    def received_inputs(self) -> list[VerifiedDraftingInput]:
        return list(self._inputs)

    def draft(self, input: VerifiedDraftingInput) -> str:
        self._inputs.append(input)
        return "[SPY_DRAFT]"


class FailingDraftingAdapter:
    """Always raises on draft(). Used for ADAPTER_FAILURE terminal path tests."""

    _ADAPTER_ID = "failing_v1"

    @property
    def adapter_id(self) -> str:
        return self._ADAPTER_ID

    def draft(self, input: VerifiedDraftingInput) -> str:
        raise RuntimeError("simulated adapter failure")
```

`DraftingService` catches `Exception` at the `adapter.draft()` call site. It does
not inspect the exception type; all adapter exceptions produce
`DraftingTerminated(ADAPTER_FAILURE)` (with the terminal audit attempt). No
sentinel exception class in `src/` is required.

`call_count` is the primary gate observable: every refusal test asserts
`call_count == 0`; every success test asserts `call_count == 1`.

No `errors.py` module is added to `src/legal_ai/drafting/`. `DraftingService`
represents all dependency failures through typed `DraftingTerminated` values;
it catches `Exception` at the two defined dependency boundaries (`audit_sink.record()`
and `adapter.draft()`) and does not need named exception classes in production
code to do so. Exception classes for test doubles are defined locally in
`tests/support/drafting_adapter.py` if needed.

Note on async: Phase 5 Slice 1 uses a synchronous adapter and service. The async
interface is deferred to the slice that introduces a live, network-backed adapter.
No `pytest-asyncio` or `anyio` dependency is needed for Slice 1.

### 6. Draft Output Contract

`DraftResult` carries `status: Literal["DRAFT"]` always.

```python
@dataclass(frozen=True, slots=True)
class DraftResult:
    status: Literal["DRAFT"]                         # Always "DRAFT"; never "APPROVED"
    draft_text: str
    adapter_id: str                                  # From adapter.adapter_id
    evidence_source_ids: tuple[str, ...]             # source_id of each _VerifiedSection
    evidence_provision_identifiers: tuple[str, ...]  # provision_identifier of each section


@dataclass(frozen=True, slots=True)
class DraftingRefused:
    code: DraftingRefusalCode


@dataclass(frozen=True, slots=True)
class DraftingTerminated:
    code: DraftingTerminalCode
```

`DraftResult` is returned to the caller and is not persisted. It must not be
approved, sent externally, stored durably, used to mutate case state or playbook
status, or used to activate a playbook by any Phase 5 code path.

### 7. Public Package API Surface

`src/legal_ai/drafting/__init__.py` exports only the vocabulary callers require
to submit drafting requests and receive results:

```
Exported:
  WaDraftingCandidate       — untrusted request candidate type
  WaDraftingRequest         — untrusted request type
  DraftResult               — success result
  DraftingRefused           — ordinary refusal result
  DraftingTerminated        — terminal failure result
  DraftingResult            — result union alias
  DraftingService           — the authorised application security boundary
  DraftingAuditSink         — Protocol for audit recording dependency
  DraftingAuditEvent        — audit event type
  DraftingRefusalCode       — typed refusal codes
  DraftingTerminalCode      — typed terminal codes
  DraftingOutcome           — typed audit outcome

Not exported (internal or test-only):
  DraftingAdapter           — internal dependency Protocol; not a public API
  VerifiedDraftingInput     — internal post-gate type; not an application entry point
  _VerifiedSection          — private; not exported
```

### 8. Real WA Fixture Behaviour

Road Traffic Act 1974 (WA) sections 55 and 56, version 14-t0-00, have
`"verified": false` in:

```
tests/fixtures/wa_legislation/road_traffic_act_1974/
  road_traffic_act_1974_consolidated_14-t0-00.sections.json
```

Gate step 5 (`section.verified is not True`) fires for any candidate that
resolves to either section. The service produces `DraftingRefused(EVIDENCE_NOT_VERIFIED)`.
The adapter is not called. A REFUSED audit event is recorded.

Tests `N-RWA-55` and `N-RWA-56` (§9 test strategy) must exercise
`DraftingService.draft()` using the actual recorded sections loaded from the
corpus. The test must verify the complete service gate path including the audit
record. These tests do not rely only on a `ValidationError` at a construction
boundary.

No code path in Phase 5 Slice 1 constructs or supplies `verified=True` for the
real WA sections. The real WA fixture files must not be modified.

Phase 5 Slice 1 positive drafting tests must use **synthetic** `RecordedSection`
objects and `RecordedWaSource` instances, constructed within
`tests/drafting/conftest.py`. These are not stored in `tests/fixtures/`.

Example synthetic builder (test-only):

```python
# tests/drafting/conftest.py — NOT tests/fixtures/
from hashlib import sha256

from legal_ai.research.models import RecordedSection, RecordedWaSource


def synthetic_section(
    identifier: str = "s 1",
    text: str = "Synthetic section text.",
    verified: bool = True,
) -> RecordedSection:
    return RecordedSection(
        identifier=identifier,
        heading="Synthetic heading",
        text=text,
        text_sha256=sha256(text.encode("utf-8")).hexdigest(),
        verified=verified,
    )
```

`verified=True` on a synthetic test fixture is an explicit test-author
declaration that this synthetic evidence represents a verified input for testing
purposes. It implies nothing about legal currency, admissibility, or verification
(see §11).

### 9. Test Strategy

#### 9.1 Mandatory positive tests (`call_count == 1` on each)

| ID | Description | Primary assertions |
|---|---|---|
| P1 | Synthetic verified candidate → `DraftResult` | `isinstance(result, DraftResult)`, `result.status == "DRAFT"`, `call_count == 1` |
| P2 | Same request twice → identical `draft_text` | `first.draft_text == second.draft_text`, `call_count == 2` |
| P3 | Provenance in `DraftResult` matches request | `evidence_source_ids` and `evidence_provision_identifiers` match candidates |
| P4 | Multiple verified candidates → `SpyDraftingAdapter` receives all sections | `len(spy.received_inputs[0].sections) == len(request.candidates)` |
| P5 | Audit sink records `DRAFTED` with adapter_id and provenance | `events[-1].outcome == DRAFTED`, `events[-1].adapter_id` set |

#### 9.2 Mandatory gate refusal tests (`call_count == 0` on every case)

| ID | Description | Expected |
|---|---|---|
| N-EMPTY | `candidates=()` | `DraftingRefused(EVIDENCE_EMPTY)` |
| N-SRC-ID | `source.source_id != packet.source_id` | `DraftingRefused(EVIDENCE_SOURCE_MISMATCH)` |
| N-SRC-ID-NONE | `source.source_id is None` | `DraftingRefused(EVIDENCE_SOURCE_MISMATCH)` |
| N-SRC-SHA256 | `source.sha256 != packet.sha256` | `DraftingRefused(EVIDENCE_SOURCE_MISMATCH)` |
| N-SRC-SHA256-NONE | `source.sha256 is None` | `DraftingRefused(EVIDENCE_SOURCE_MISMATCH)` |
| N-SRC-CONTENT | `sha256(source.source_content) != packet.sha256` | `DraftingRefused(EVIDENCE_SOURCE_MISMATCH)` |
| N-SRC-SYS | `source.source_system != packet.source_system` | `DraftingRefused(EVIDENCE_SOURCE_MISMATCH)` |
| N-SRC-SYS-NONE | `source.source_system is None` | `DraftingRefused(EVIDENCE_SOURCE_MISMATCH)` |
| N-SRC-JURI | `source.jurisdiction != packet.jurisdiction` | `DraftingRefused(EVIDENCE_SOURCE_MISMATCH)` |
| N-SRC-JURI-NONE | `source.jurisdiction is None` | `DraftingRefused(EVIDENCE_SOURCE_MISMATCH)` |
| N-PROV | provision_identifier not in source.sections | `DraftingRefused(EVIDENCE_PROVISION_MISMATCH)` |
| N-VER-F | `section.verified=False` | `DraftingRefused(EVIDENCE_NOT_VERIFIED)` |
| N-VER-1 | `section.verified=1` (int; dataclass allows) | `DraftingRefused(EVIDENCE_NOT_VERIFIED)` |
| N-VER-STR | `section.verified="true"` (str) | `DraftingRefused(EVIDENCE_NOT_VERIFIED)` |
| N-VER-NONE | `section.verified=None` | `DraftingRefused(EVIDENCE_NOT_VERIFIED)` |
| N-HASH | `text_sha256` does not match section text | `DraftingRefused(EVIDENCE_HASH_MISMATCH)` |
| N-DUP | Same provision_identifier, same text | `DraftingRefused(EVIDENCE_DUPLICATE_PROVISION)` |
| N-CONF | Same provision_identifier, different texts | `DraftingRefused(EVIDENCE_CONFLICT)` |
| N-MULTI-VER | One verified + one `verified=False` candidate | `DraftingRefused(EVIDENCE_NOT_VERIFIED)` |
| N-MULTI-HASH | One verified + one hash-mismatched candidate | `DraftingRefused(EVIDENCE_HASH_MISMATCH)` |
| N-PARTIAL | Any refusal path | Result is `DraftingRefused` or `DraftingTerminated`, never `DraftResult` |
| N-RWA-55 | Real WA s 55 via `DraftingService.draft()` | `DraftingRefused(EVIDENCE_NOT_VERIFIED)`, audit REFUSED recorded |
| N-RWA-56 | Real WA s 56 via `DraftingService.draft()` | `DraftingRefused(EVIDENCE_NOT_VERIFIED)`, audit REFUSED recorded |
| N-REFUSE-AUDIT | Refusal is audited before return | `audit_sink.events[-1].outcome == REFUSED`, `events[-1].refusal_code` matches |

#### 9.3 Mandatory terminal tests

| ID | Description | Expected |
|---|---|---|
| T-NO-SINK | `audit_sink=None` → no further work | `DraftingTerminated(AUDIT_SINK_UNAVAILABLE)`, `call_count == 0` |
| T-SINK-REFUSE | `UnavailableDraftingAuditSink` raises during refusal audit | `DraftingTerminated(AUDIT_SINK_UNAVAILABLE)`, `call_count == 0` |
| T-SINK-DRAFT | `UnavailableDraftingAuditSink` raises after adapter success | `DraftingTerminated(AUDIT_SINK_UNAVAILABLE)`, no `DraftResult` returned |
| T-ADAPT-FAIL | `FailingDraftingAdapter` raises, terminal audit succeeds | `DraftingTerminated(ADAPTER_FAILURE)` |
| T-ADAPT-FAIL-SINK | `FailingDraftingAdapter` raises, terminal audit also raises | `DraftingTerminated(AUDIT_SINK_UNAVAILABLE)` |
| T-NO-ESCAPE | Audit-sink and adapter operational failures at dependency boundaries | No `audit_sink.record()` or `adapter.draft()` exception escapes `DraftingService.draft()` uncontrolled; all return `DraftingTerminated` |

Note on T-NO-ESCAPE: The claim is that `audit_sink.record()` and `adapter.draft()`
exceptions are caught at their respective dependency call sites and converted to
`DraftingTerminated`. This does not mean every conceivable programming defect
inside `DraftingService` is converted to `DraftingResult`. Internal programming
defects outside those two dependency boundaries are not deliberately swallowed
and may propagate normally.

#### 9.4 Mandatory adversarial tests

| ID | Description | Expected |
|---|---|---|
| A-INJECT | Prompt injection string in `purpose` field | Draft proceeds; injected text appears verbatim in `draft_text` only; service behaviour unchanged; `call_count == 1` |

#### 9.5 Mandatory regression tests

| ID | Description | Expected |
|---|---|---|
| R1 | All 843 existing unit tests pass | No Phase 4 file modified |
| R2 | `RecordedSection.verified` is `bool` (not `Literal[True]`) | Corpus loader contract unchanged |
| R3 | `FailClosedGroundingGate.assert_may_activate()` raises unconditionally | Playbook grounding gate untouched |
| R4 | `WaEvidencePacket` schema unchanged | No field added, removed, or renamed |
| R5 | PostgreSQL integration suite: 144 tests pass | No migration, no schema change |

### 10. Audit Contract

#### 10.1 DraftingAuditEvent

`DraftingAuditEvent` is a Pydantic `BaseModel` with a `model_validator` that
makes contradictory audit events invalid at construction.

```python
class DraftingAuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    outcome: DraftingOutcome
    refusal_code: DraftingRefusalCode | None = None
    terminal_code: DraftingTerminalCode | None = None
    matter_id: UUID
    adapter_id: str | None = None
    evidence_source_ids: tuple[str, ...] | None = None
    evidence_provision_identifiers: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _enforce_consistency(self) -> "DraftingAuditEvent":
        match self.outcome:
            case DraftingOutcome.DRAFTED:
                if self.refusal_code is not None:
                    raise ValueError("DRAFTED event must not carry refusal_code")
                if self.terminal_code is not None:
                    raise ValueError("DRAFTED event must not carry terminal_code")
                if self.adapter_id is None:
                    raise ValueError("DRAFTED event must carry adapter_id")
                if self.evidence_source_ids is None:
                    raise ValueError("DRAFTED event must carry evidence_source_ids")
            case DraftingOutcome.REFUSED:
                if self.refusal_code is None:
                    raise ValueError("REFUSED event must carry refusal_code")
                if self.terminal_code is not None:
                    raise ValueError("REFUSED event must not carry terminal_code")
            case DraftingOutcome.TERMINATED:
                if self.terminal_code is None:
                    raise ValueError("TERMINATED event must carry terminal_code")
                if self.refusal_code is not None:
                    raise ValueError("TERMINATED event must not carry refusal_code")
                if self.adapter_id is not None:
                    raise ValueError("TERMINATED event must not carry adapter_id")
        return self
```

#### 10.2 DraftingAuditSink Protocol

```python
@runtime_checkable
class DraftingAuditSink(Protocol):
    def record(self, event: DraftingAuditEvent) -> None: ...
```

#### 10.3 DraftingService sequencing

The exact sequencing within `DraftingService.draft()`:

```
A. Check audit sink exists (gate step 1).
   If audit_sink is None → return DraftingTerminated(AUDIT_SINK_UNAVAILABLE).
   No further work.

B. Evaluate evidence (gate steps 2–8).
   Identify the first failing step, if any.

C. If an ordinary refusal was found:
   1. Construct REFUSED DraftingAuditEvent with refusal_code.
   2. try: audit_sink.record(event)
      except Exception: return DraftingTerminated(AUDIT_SINK_UNAVAILABLE)
   3. return DraftingRefused(code)

D. All gate steps passed.
   Construct VerifiedDraftingInput.

E. try: draft_text = adapter.draft(verified_input)
   except Exception:
     1. Construct TERMINATED DraftingAuditEvent with ADAPTER_FAILURE.
     2. try: audit_sink.record(terminal_event)
        except Exception: return DraftingTerminated(AUDIT_SINK_UNAVAILABLE)
     3. return DraftingTerminated(ADAPTER_FAILURE)

F. Adapter succeeded.
   1. Construct DraftResult.
   2. Construct DRAFTED DraftingAuditEvent with adapter_id and provenance.
   3. try: audit_sink.record(drafted_event)
      except Exception:
        discard DraftResult
        return DraftingTerminated(AUDIT_SINK_UNAVAILABLE)
   4. return DraftResult
```

Exceptions from `audit_sink.record()` and `adapter.draft()` are caught at
their respective call sites and converted to `DraftingTerminated`. Internal
programming defects outside those two dependency boundaries are not deliberately
swallowed.

#### 10.4 Test doubles

`tests/support/drafting_audit.py` provides:

- `InMemoryDraftingAuditSink` — records events in a list for assertion
- `UnavailableDraftingAuditSink` — raises `RuntimeError` on every `record()` call;
  used for terminal path tests T-SINK-REFUSE, T-SINK-DRAFT, T-ADAPT-FAIL-SINK

### 11. Service Boundary

`DraftingService` is the authorised application security boundary for all
drafting operations in Phase 5 Slice 1.

- `DraftingAdapter` is an internal dependency, not a supported application entry
  point. Calling `adapter.draft()` directly without passing through
  `DraftingService` bypasses the evidence gate, the audit requirement, and the
  fail-closed termination logic. This is not a supported usage pattern.
- `src/legal_ai/drafting/adapters.py` must not expose a helper that performs
  drafting without the service gate.
- `src/legal_ai/drafting/__init__.py` does not export `DraftingAdapter` or
  `VerifiedDraftingInput` and must not promote adapter invocation as a public
  workflow.
- Slice 1 contains no production adapter implementation and no production
  drafting wiring. Future slices that introduce a live adapter must separately
  demonstrate — in their own ADR and wiring test — that all invocation paths
  pass through `DraftingService`.

### 12. Verification Admission Signal

`RecordedSection.verified = True` is a **structural admission signal** recorded
in untrusted fixture data. It is the signal that a section's text is eligible
for consideration as evidence in the drafting gate.

Slice 1 verifies only:

- the signal is exactly the Python `True` singleton (`verified is True`);
- the packet source identity, content hash, and provision cross-reference are
  structurally consistent with the source record; and
- the section text has not changed relative to its recorded digest.

Slice 1 does **not** prove, and must not claim to prove:

- who performed any human review of the extracted text;
- whether a human actually compared the extracted text against the official
  source document;
- when any verification occurred;
- which edition of the source was used for that verification;
- whether the law reflected in the text is still in force; or
- that the section text is legally correct, accurate, or admissible.

Consequently:

- Successful Phase 5 Slice 1 drafting is **synthetic and test-only**. No
  positive drafting path uses real WA section body text.
- No successful production real-WA drafting path is authorised in Slice 1.
- Real WA ss 55–56 remain refusal-only fixtures.
- A future separately authorised verification/attestation workflow is required
  before real statutory text can be admitted to successful drafting.
- Digest integrity alone (`text_sha256`) does not constitute verification.

### 13. Authorised File List

**Files to create (new — 15 files):**

```
src/legal_ai/drafting/__init__.py
src/legal_ai/drafting/types.py
src/legal_ai/drafting/models.py
src/legal_ai/drafting/audit.py
src/legal_ai/drafting/adapters.py
src/legal_ai/drafting/service.py
tests/drafting/__init__.py
tests/drafting/conftest.py
tests/drafting/test_gate.py
tests/drafting/test_service.py
tests/drafting/test_adversarial.py
tests/drafting/test_real_wa_fixture.py
tests/drafting/test_audit.py
tests/support/drafting_audit.py
tests/support/drafting_adapter.py
```

Note: no `src/legal_ai/drafting/errors.py`. No named exception classes are
required in production code (see §5).

**Files to modify (update):**

None. The implementation PR must contain only the authorised drafting
implementation and test files listed above. After the implementation PR is
independently reviewed and merged, completion/status reconciliation of
`docs/execution/IMPLEMENTATION_STATUS.md` must be handled separately as the
smallest documentation-only follow-up, consistent with existing repository
governance.

**Files that must NOT be touched:**

```
src/legal_ai/research/          (all files — entirely untouched)
src/legal_ai/playbooks/grounding.py
src/legal_ai/__init__.py
tests/fixtures/                 (all files — verified flags remain false)
tests/research/                 (all files)
tests/support/research_audit.py (existing support file; untouched)
alembic/                        (no migration)
pyproject.toml                  (no new dependency)
PROJECT_GOVERNANCE.md
ENGINEERING_WORKFLOW.md
docs/execution/MVP_ROADMAP.md
docs/execution/CASEWORK_OS_ROADMAP.md
docs/adr/0001 through 0014     (existing accepted ADRs)
```

### 14. Explicit Non-Goals

The following are explicitly deferred and must not be implemented in Phase 5
Slice 1, even partially or as stubs:

- **Live model providers** — no Anthropic, OpenAI, Google, Cohere, or other
  API-backed adapter; no LLM SDK added to `pyproject.toml`
- **Async model protocol** — deferred to the slice that introduces a
  network-backed real adapter; Slice 1 uses a synchronous interface
- **Live statutory retrieval** — no runtime network path to any legislation source
- **Human verification workflow** — no mechanism for setting `RecordedSection.verified=True`
  in the real WA fixture or any other corpus file
- **Setting real WA sections `verified=True`** — requires a separate independent
  human verification step outside this ADR's scope
- **Production adapter** — no implementation of `DraftingAdapter` in `src/`
- **Production drafting wiring** — the service is exercised entirely through
  injected test doubles; no wired entry point exists in Slice 1
- **Production audit storage** — no database write for drafting audit events
- **Durable draft storage** — no database table, filesystem write, or
  object-store write for draft output
- **Approval workflow** — no draft-to-approved transition, no `APPROVED` status
- **External dispatch** — no sending, emailing, filing, submitting, or signing
  any draft content
- **API or UI** — no FastAPI endpoint, HTTP route, WebSocket, CLI, or browser
  interface
- **Agent autonomy or tool use** — no shell, browser, filesystem, email, or
  other tool access
- **pgvector or embeddings** — no vector store, semantic search, or embedding
- **L3+ authority** — no external action, no standing authority, no approval
  delegation
- **Playbook activation** — `FailClosedGroundingGate` is untouched and
  refuse-closed throughout; Phase 5 Slice 1 does not change this

### 15. Rollback

Phase 5 Slice 1 is fully isolated from Phases 1–4. Rollback requires:

1. Delete `src/legal_ai/drafting/` entirely.
   No other `src/` module imports from it.
2. Delete `tests/drafting/` entirely.
3. Delete `tests/support/drafting_audit.py` and `tests/support/drafting_adapter.py`.
4. Revert the Phase 5 status entry in `docs/execution/IMPLEMENTATION_STATUS.md`.
5. Retain `docs/adr/0015-...md` as a historical record.

No `alembic downgrade` is required. No `pyproject.toml` change is required.
Phases 1–4 behaviour is entirely unchanged after rollback.

### 16. Authorisation Boundary

Acceptance of ADR 0015 by the owner authorises the Phase 5 Slice 1
**architecture** described in this document. It does not authorise implementation.

The authorisation sequence is:

1. Owner accepts ADR 0015 → ADR file is committed on a documentation-only branch
   and merged to `main` via the normal PR review process.
2. Only after ADR 0015 is on `main` may the owner separately issue and authorise
   the bounded Phase 5 Slice 1 Work Packet.
3. Only after the Work Packet is explicitly authorised may the implementation
   branch, production drafting files, or any test drafting files be created.

No implementation branch or production/test drafting files may be created merely
because the ADR is accepted. Per `ENGINEERING_WORKFLOW.md §2`, the next phase
does not start merely because a previous phase's ADR is accepted.

The Work Packet must state:

- the exact feature branch name
- the exact starting main SHA
- explicit confirmation that implementation is authorised under ADR 0015

## Consequences

- Real drafting against ss 55–56 of the Road Traffic Act 1974 (WA) remains
  blocked until an independent human verification of the extracted text is
  performed and recorded as `"verified": true` in the sections fixture under a
  separately authorised process.
- `RecordedSection.verified` remains `bool`; Phase 4 contracts are unchanged.
- Digest integrity alone (`text_sha256`) does not constitute verification.
- `FailClosedGroundingGate` remains untouched and refuse-closed throughout
  Phase 5 Slice 1.
- No production adapter implementation is included; the service is exercised
  entirely through injected test doubles.
- `DraftingService.draft()` catches exceptions only at the two defined
  dependency boundaries (`audit_sink.record()` and `adapter.draft()`); it does
  not swallow internal programming defects.
- Phase 6 (approval service) may not begin until Phase 5 Slice 1 is merged and
  a Phase 6 ADR is separately accepted by the owner.
- `EvidenceItem` with `verified: Literal[True]` as the untrusted request boundary
  is explicitly rejected by this ADR.
- Caller-constructed `WaDraftingCandidate` pairs that are internally consistent
  (forged source and packet with matching hashes) pass the structural consistency
  gate. This limitation is accepted for Slice 1 (synthetic tests only; no
  production wiring) and must be addressed in the slice that introduces a live
  adapter.

"""Phase 4 Slice 1: deterministic, read-only WA research over recorded fixtures.

Standalone module per ADR 0013. No live retrieval, no network access, no model
use, no persistence, and no production wiring.
"""

from .audit import ResearchAuditEvent, ResearchAuditSink
from .corpus import RecordedSourceCorpus, RecordedWaCorpus
from .errors import (
    AmbiguousSelection,
    RecordedCorpusError,
    ResearchAuditSinkUnavailable,
    ResearchError,
)
from .models import (
    ActIdentity,
    RecordedProvision,
    RecordedWaSource,
    ResearchQuery,
    WaEvidencePacket,
)
from .service import (
    ResearchRefused,
    ResearchResult,
    ResearchTerminated,
    ResearchValidated,
    WaResearchService,
)
from .types import (
    WA_ALLOWLISTED_HOSTS,
    WA_JURISDICTION,
    WA_SOURCE_SYSTEM,
    LegalStatus,
    ResearchAuditResult,
    ResearchOutcome,
    ResearchRefusalCode,
    ResearchTerminalCode,
)
from .validation import validate_recorded_source

__all__ = [
    "WA_ALLOWLISTED_HOSTS",
    "WA_JURISDICTION",
    "WA_SOURCE_SYSTEM",
    "ActIdentity",
    "AmbiguousSelection",
    "LegalStatus",
    "RecordedCorpusError",
    "RecordedProvision",
    "RecordedSourceCorpus",
    "RecordedWaCorpus",
    "RecordedWaSource",
    "ResearchAuditEvent",
    "ResearchAuditResult",
    "ResearchAuditSink",
    "ResearchAuditSinkUnavailable",
    "ResearchError",
    "ResearchOutcome",
    "ResearchQuery",
    "ResearchRefusalCode",
    "ResearchRefused",
    "ResearchResult",
    "ResearchTerminalCode",
    "ResearchTerminated",
    "ResearchValidated",
    "WaEvidencePacket",
    "WaResearchService",
    "validate_recorded_source",
]

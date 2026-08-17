"""Phase 4 WA research over recorded fixtures (Slices 1 and 2).

Standalone module per ADR 0013 and ADR 0014. No live retrieval, no network
access, no model use, no persistence, and no production wiring.
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
    RecordedSection,
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
    "RecordedSection",
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

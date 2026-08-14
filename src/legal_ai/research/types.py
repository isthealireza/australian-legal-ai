"""Closed Phase 4 WA research vocabularies and source constants.

These vocabularies are WA-specific. They are deliberately separate from the
`federal_register` provenance schema, which ADR 0013 records as not reusable as
a WA evidence contract.
"""

from enum import StrEnum
from typing import Final

WA_SOURCE_SYSTEM: Final = "wa_legislation"
WA_JURISDICTION: Final = "WA"

#: Closed, exact HTTPS hostname allowlist from ADR 0013 §3. No wildcard
#: subdomain is trusted and no other host is permitted.
WA_ALLOWLISTED_HOSTS: Final = frozenset(
    {
        "legislation.wa.gov.au",
        "www.legislation.wa.gov.au",
    }
)

#: Recorded provenance values that explicitly assert an unknown state. These
#: never satisfy a required field.
UNKNOWN_SENTINELS: Final = frozenset({"unknown", "unspecified", "n/a", "tbd"})


class ResearchRefusalCode(StrEnum):
    """Typed reason codes for ordinary, total refusal."""

    RETRIEVAL_MISSING = "RETRIEVAL_MISSING"
    SELECTION_AMBIGUOUS = "SELECTION_AMBIGUOUS"
    FIELD_MISSING = "FIELD_MISSING"
    FIELD_INVALID = "FIELD_INVALID"
    SOURCE_SYSTEM_MISMATCH = "SOURCE_SYSTEM_MISMATCH"
    JURISDICTION_MISMATCH = "JURISDICTION_MISMATCH"
    SOURCE_NOT_ALLOWLISTED = "SOURCE_NOT_ALLOWLISTED"
    VERSION_MISSING = "VERSION_MISSING"
    STATUS_UNKNOWN = "STATUS_UNKNOWN"
    STATUS_DATE_INVALID = "STATUS_DATE_INVALID"
    CITATION_NOT_FOUND = "CITATION_NOT_FOUND"
    PINPOINT_MISMATCH = "PINPOINT_MISMATCH"
    HASH_MISMATCH = "HASH_MISMATCH"


class ResearchTerminalCode(StrEnum):
    """Terminal failure codes. These are never ordinary refusals."""

    AUDIT_SINK_UNAVAILABLE = "AUDIT_SINK_UNAVAILABLE"


class LegalStatus(StrEnum):
    """Recorded effective, commencement, or repeal status of a source version."""

    IN_FORCE = "IN_FORCE"
    COMMENCED = "COMMENCED"
    REPEALED = "REPEALED"
    UNKNOWN = "UNKNOWN"


class ResearchOutcome(StrEnum):
    """Audited outcome of one deterministic research evaluation."""

    VALIDATED = "VALIDATED"
    REFUSED = "REFUSED"


class ResearchAuditResult(StrEnum):
    """Audit state carried by a validated evidence packet."""

    RECORDED = "RECORDED"

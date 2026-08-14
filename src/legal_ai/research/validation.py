"""Deterministic validation of one recorded WA source against one query.

Every check here is deterministic code, never a model: field presence,
jurisdiction and source-system comparison, host allowlisting, version and
status validation, SHA-256 recomputation, citation existence, and pinpoint
integrity (`PROJECT_GOVERNANCE.md` §2.3).

Recorded text is untrusted data. It is only ever compared, hashed, or copied
into a packet; it is never interpreted as an instruction, and no recorded value
can widen the allowlists or skip a check.

Check order is fixed and total. A source must first prove it is an allowlisted,
identifiable WA source; then that its provenance (version, status) is exact;
then that its content is intact; only then is the citation looked up. A source
that fails integrity therefore never reports a citation-level result.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

from pydantic import ValidationError

from .corpus import normalize_for_match
from .models import PacketDraft, RecordedProvision, RecordedWaSource, ResearchQuery
from .types import (
    UNKNOWN_SENTINELS,
    WA_ALLOWLISTED_HOSTS,
    WA_JURISDICTION,
    WA_SOURCE_SYSTEM,
    LegalStatus,
    ResearchRefusalCode,
)

_IN_FORCE_CURRENCIES = frozenset({"current", "in force", "in-force"})
_COMMENCED_CURRENCIES = frozenset({"commenced"})
_REPEALED_CURRENCIES = frozenset({"repealed"})


def _stated(value: str | None) -> str | None:
    """Return the recorded value only if it states something exact."""

    if value is None:
        return None
    collapsed = " ".join(value.split())
    if not collapsed or collapsed.casefold() in UNKNOWN_SENTINELS:
        return None
    return value


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _parse_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        return None
    return parsed


def _url_refusal(value: str) -> ResearchRefusalCode | None:
    if value != value.strip() or any(ord(character) < 32 for character in value):
        return ResearchRefusalCode.FIELD_INVALID
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return ResearchRefusalCode.FIELD_INVALID
    if (
        parsed.scheme != "https"
        or parsed.hostname not in WA_ALLOWLISTED_HOSTS
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        return ResearchRefusalCode.SOURCE_NOT_ALLOWLISTED
    return None


def _legal_status(currency: str | None, in_force: bool | None) -> LegalStatus:
    """Map recorded status metadata to a status, refusing any inconsistency."""

    stated = _stated(currency)
    if stated is None or in_force is None:
        return LegalStatus.UNKNOWN
    key = normalize_for_match(stated)
    if key in _IN_FORCE_CURRENCIES and in_force:
        return LegalStatus.IN_FORCE
    if key in _COMMENCED_CURRENCIES and in_force:
        return LegalStatus.COMMENCED
    if key in _REPEALED_CURRENCIES and not in_force:
        return LegalStatus.REPEALED
    return LegalStatus.UNKNOWN


def _find_provision(
    source: RecordedWaSource, requested_identifier: str
) -> RecordedProvision | None:
    """Match a request against the exact recorded citation forms only."""

    wanted = normalize_for_match(requested_identifier)
    for provision in source.provisions:
        if wanted in {
            normalize_for_match(provision.identifier),
            normalize_for_match(provision.pinpoint),
        }:
            return provision
    return None


def validate_recorded_source(
    query: ResearchQuery, source: RecordedWaSource
) -> PacketDraft | ResearchRefusalCode:
    """Return validated packet fields, or the typed reason to refuse totally."""

    # 1. Source identity and allowlisting.
    source_system = _stated(source.source_system)
    if source_system is None:
        return ResearchRefusalCode.FIELD_MISSING
    if source_system != WA_SOURCE_SYSTEM:
        return ResearchRefusalCode.SOURCE_SYSTEM_MISMATCH

    jurisdiction = _stated(source.jurisdiction)
    act_jurisdiction = _stated(source.act_jurisdiction)
    if jurisdiction is None or act_jurisdiction is None:
        return ResearchRefusalCode.FIELD_MISSING
    if jurisdiction != WA_JURISDICTION or act_jurisdiction != WA_JURISDICTION:
        return ResearchRefusalCode.JURISDICTION_MISMATCH

    source_id = _stated(source.source_id)
    act_title = _stated(source.act_title)
    if source_id is None or act_title is None:
        return ResearchRefusalCode.FIELD_MISSING

    official_source_url = _stated(source.official_source_url)
    if official_source_url is None:
        return ResearchRefusalCode.FIELD_MISSING
    url_refusal = _url_refusal(official_source_url)
    if url_refusal is not None:
        return url_refusal

    # 2. Provenance: a source version or a compilation date, and an exact status.
    source_version = _stated(source.source_version)
    recorded_compilation_date = _stated(source.compilation_date)
    compilation_date = None
    if recorded_compilation_date is not None:
        compilation_date = _parse_date(recorded_compilation_date)
        if compilation_date is None:
            return ResearchRefusalCode.FIELD_INVALID
    if source_version is None and compilation_date is None:
        return ResearchRefusalCode.VERSION_MISSING

    legal_status = _legal_status(source.status_currency, source.status_in_force)
    if legal_status is LegalStatus.UNKNOWN:
        return ResearchRefusalCode.STATUS_UNKNOWN
    recorded_status_date = _stated(source.status_date)
    if recorded_status_date is None:
        return ResearchRefusalCode.FIELD_MISSING
    status_date = _parse_date(recorded_status_date)
    if status_date is None:
        return ResearchRefusalCode.STATUS_DATE_INVALID

    # 3. Content integrity: exact bytes, exact retrieval time, recomputed digest.
    if not source.source_content:
        return ResearchRefusalCode.FIELD_MISSING

    recorded_retrieved_at = _stated(source.retrieved_at)
    if recorded_retrieved_at is None:
        return ResearchRefusalCode.FIELD_MISSING
    retrieved_at = _parse_utc(recorded_retrieved_at)
    if retrieved_at is None:
        return ResearchRefusalCode.FIELD_INVALID
    if status_date > retrieved_at.date():
        return ResearchRefusalCode.STATUS_DATE_INVALID

    recorded_sha256 = _stated(source.sha256)
    if recorded_sha256 is None:
        return ResearchRefusalCode.FIELD_MISSING
    if len(recorded_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in recorded_sha256
    ):
        return ResearchRefusalCode.FIELD_INVALID
    if hashlib.sha256(source.source_content).hexdigest() != recorded_sha256:
        return ResearchRefusalCode.HASH_MISMATCH

    # 4. Citation existence, then pinpoint integrity, against recorded forms only.
    provision = _find_provision(source, query.provision_identifier)
    if provision is None:
        return ResearchRefusalCode.CITATION_NOT_FOUND
    if normalize_for_match(query.pinpoint) != normalize_for_match(provision.pinpoint):
        return ResearchRefusalCode.PINPOINT_MISMATCH

    draft = PacketDraft(
        source_id=source_id,
        official_source_url=official_source_url,
        act_title=act_title,
        act_number=_stated(source.act_number),
        provision_identifier=provision.identifier,
        pinpoint=provision.pinpoint,
        provision_heading=_stated(provision.heading),
        source_version=source_version,
        compilation_date=compilation_date,
        legal_status=legal_status,
        status_date=status_date,
        source_content=source.source_content,
        retrieved_at=retrieved_at,
        sha256=recorded_sha256,
    )
    try:
        # Defence in depth: prove the packet contract holds before any audit
        # event claims a validated outcome. The trial packet is discarded.
        draft.to_packet()
    except ValidationError:
        return ResearchRefusalCode.FIELD_INVALID
    return draft

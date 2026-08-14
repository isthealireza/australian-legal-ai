"""Strict WA evidence-packet contract, queries, and recorded-source records.

The WA evidence packet is a new, WA-specific, in-memory contract (ADR 0013 §4).
It is deliberately not the `federal_register` provenance schema and shares no
model with it, so the whole slice can be rolled back by deleting this module.

`RecordedWaSource` and `RecordedProvision` hold **untrusted** recorded fixture
data. Nothing in them is trusted until `validation.py` has checked it field by
field; text inside them is data and never instruction.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

from .types import (
    WA_ALLOWLISTED_HOSTS,
    WA_JURISDICTION,
    WA_SOURCE_SYSTEM,
    LegalStatus,
    ResearchAuditResult,
)

_STRICT = ConfigDict(extra="forbid", strict=True, frozen=True)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MAX_SOURCE_CONTENT_BYTES = 104_857_600


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must contain a non-whitespace character")
    return value


def validate_wa_sha256(value: str) -> str:
    """Return an exact lowercase SHA-256 digest or reject it."""

    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError("SHA-256 must be exactly 64 lowercase hexadecimal characters")
    return value


def validate_wa_official_source_url(value: str) -> str:
    """Return an HTTPS URL on the closed WA host allowlist, or reject it."""

    if value != value.strip() or any(ord(character) < 32 for character in value):
        raise ValueError(
            "official source URL contains surrounding whitespace or control characters"
        )
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("official source URL is malformed") from exc
    if parsed.scheme != "https":
        raise ValueError("official source URL must use HTTPS")
    if (
        parsed.hostname not in WA_ALLOWLISTED_HOSTS
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("official source URL must use an allowlisted WA legislation host")
    return value


ExactIdentifier = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=255),
    AfterValidator(_nonblank),
]
ExactText = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=4096),
    AfterValidator(_nonblank),
]
WaOfficialSourceUrl = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=2048),
    AfterValidator(validate_wa_official_source_url),
]
WaSha256Digest = Annotated[
    str,
    StringConstraints(strict=True),
    AfterValidator(validate_wa_sha256),
]


class ActIdentity(BaseModel):
    """Named WA instrument identity carried by a validated packet."""

    model_config = _STRICT

    title: ExactText
    jurisdiction: Literal["WA"]
    act_number: ExactIdentifier | None = None


class ResearchQuery(BaseModel):
    """One deterministic, read-only research request over recorded fixtures."""

    model_config = _STRICT

    jurisdiction: ExactIdentifier
    act_title: ExactText
    provision_identifier: ExactIdentifier
    pinpoint: ExactIdentifier


class WaEvidencePacket(BaseModel):
    """A fully validated WA evidence packet.

    Construction is only reachable after deterministic validation *and* a
    recorded audit event: `audit_result` admits exactly one value. A packet is
    therefore never partial, never unaudited, and never hash-inconsistent.
    """

    model_config = _STRICT

    source_id: ExactIdentifier
    source_system: Literal["wa_legislation"]
    jurisdiction: Literal["WA"]
    official_source_url: WaOfficialSourceUrl
    act: ActIdentity
    provision_identifier: ExactIdentifier
    pinpoint: ExactIdentifier
    provision_heading: ExactText | None
    source_version: ExactIdentifier | None
    compilation_date: date | None
    legal_status: LegalStatus
    status_date: date
    source_content: bytes
    retrieved_at: datetime
    sha256: WaSha256Digest
    audit_result: Literal[ResearchAuditResult.RECORDED]

    @field_validator("legal_status")
    @classmethod
    def _reject_unknown_status(cls, value: LegalStatus) -> LegalStatus:
        if value is LegalStatus.UNKNOWN:
            raise ValueError("legal status must be known")
        return value

    @field_validator("retrieved_at")
    @classmethod
    def _require_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("retrieval timestamp must be timezone-aware UTC")
        return value

    @field_validator("source_content")
    @classmethod
    def _require_bounded_content(cls, value: bytes) -> bytes:
        if not value:
            raise ValueError("source content must not be empty")
        if len(value) > MAX_SOURCE_CONTENT_BYTES:
            raise ValueError("source content exceeds the maximum packet size")
        return value

    @model_validator(mode="after")
    def _require_consistent_packet(self) -> WaEvidencePacket:
        if self.source_version is None and self.compilation_date is None:
            raise ValueError("a source version or a compilation date is required")
        if self.act.jurisdiction != WA_JURISDICTION:
            raise ValueError("act identity jurisdiction must be WA")
        if hashlib.sha256(self.source_content).hexdigest() != self.sha256:
            raise ValueError("packet SHA-256 does not match the exact source content")
        if self.status_date > self.retrieved_at.date():
            raise ValueError("status date must not postdate the retrieval timestamp")
        return self


@dataclass(frozen=True, slots=True)
class PacketDraft:
    """Validated packet fields held before the required audit event.

    This is internal to the module and is never returned to a caller: no packet
    may leave the boundary until its audit event has been recorded.
    """

    source_id: str
    official_source_url: str
    act_title: str
    act_number: str | None
    provision_identifier: str
    pinpoint: str
    provision_heading: str | None
    source_version: str | None
    compilation_date: date | None
    legal_status: LegalStatus
    status_date: date
    source_content: bytes
    retrieved_at: datetime
    sha256: str

    def to_packet(self) -> WaEvidencePacket:
        """Build the immutable packet once the audit event has been recorded."""

        return WaEvidencePacket(
            source_id=self.source_id,
            source_system=WA_SOURCE_SYSTEM,
            jurisdiction=WA_JURISDICTION,
            official_source_url=self.official_source_url,
            act=ActIdentity(
                title=self.act_title,
                jurisdiction=WA_JURISDICTION,
                act_number=self.act_number,
            ),
            provision_identifier=self.provision_identifier,
            pinpoint=self.pinpoint,
            provision_heading=self.provision_heading,
            source_version=self.source_version,
            compilation_date=self.compilation_date,
            legal_status=self.legal_status,
            status_date=self.status_date,
            source_content=self.source_content,
            retrieved_at=self.retrieved_at,
            sha256=self.sha256,
            audit_result=ResearchAuditResult.RECORDED,
        )


@dataclass(frozen=True, slots=True)
class RecordedProvision:
    """One provision recorded as a pinpoint in a fixture manifest. Untrusted."""

    identifier: str
    pinpoint: str
    heading: str | None


@dataclass(frozen=True, slots=True)
class RecordedWaSource:
    """One recorded WA fixture: raw manifest metadata plus exact content bytes.

    Every field is untrusted recorded data. Values stay as recorded (raw
    strings, no coercion) so that `validation.py` performs every semantic check
    and can refuse with a precise typed code.
    """

    source_id: str | None
    source_system: str | None
    jurisdiction: str | None
    act_title: str | None
    act_jurisdiction: str | None
    act_number: str | None
    official_source_url: str | None
    provisions: tuple[RecordedProvision, ...]
    source_version: str | None
    compilation_date: str | None
    status_currency: str | None
    status_in_force: bool | None
    status_date: str | None
    retrieved_at: str | None
    sha256: str | None
    source_content: bytes

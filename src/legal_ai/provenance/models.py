"""Strict domain models for Federal Register artifact provenance."""

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from legal_ai.sources.frl.models import FederalRegisterId

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_APPROVED_FEDERAL_REGISTER_HOSTS = frozenset(
    {
        "api.prod.legislation.gov.au",
        "legislation.gov.au",
    }
)


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must contain a non-whitespace character")
    return value


def validate_sha256(value: str) -> str:
    """Return an exact lowercase SHA-256 digest or reject it."""

    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError("SHA-256 must be exactly 64 lowercase hexadecimal characters")
    return value


def _validate_official_url(value: str) -> str:
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
        parsed.hostname not in _APPROVED_FEDERAL_REGISTER_HOSTS
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("official source URL must use an approved Federal Register host")
    return value


ExactIdentifier = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=255),
    AfterValidator(_reject_blank),
]
ExactHeader = Annotated[str, StringConstraints(strict=True, max_length=4096)]
ExactMediaType = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=255),
    AfterValidator(_reject_blank),
]
OfficialSourceUrl = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=2048),
    AfterValidator(_validate_official_url),
]
Sha256Digest = Annotated[
    str,
    StringConstraints(strict=True),
    AfterValidator(validate_sha256),
]
VolumeNumber = Annotated[int, Field(strict=True, ge=0)]


class FederalRegisterCapture(BaseModel):
    """Immutable, validated provenance submitted with official document bytes."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_system: Literal["federal_register"] = "federal_register"
    title_id: FederalRegisterId
    register_id: FederalRegisterId
    official_document_id: ExactIdentifier
    official_source_url: OfficialSourceUrl
    document_format: Literal["Word", "Pdf", "Epub", "NameOnly"]
    volume: VolumeNumber | None = None
    response_content_type: ExactMediaType
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    etag: ExactHeader | None = None
    last_modified: ExactHeader | None = None
    expected_sha256: Sha256Digest | None = None

    @field_validator("retrieved_at")
    @classmethod
    def _require_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("retrieval timestamp must be timezone-aware UTC")
        return value

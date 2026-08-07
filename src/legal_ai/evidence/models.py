"""Strict commands and immutable records for matter evidence."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from legal_ai.casework.types import ActorRef

from .errors import UnsafeFilename
from .types import EvidenceKind, EvidenceReviewStatus, EvidenceRole

MAX_EVIDENCE_BYTES = 104_857_600
MAX_IMAGE_DIMENSION_PX = 100_000
MAX_VIDEO_DIMENSION_PX = 100_000
MAX_VIDEO_DURATION_MS = 604_800_000
MAX_SUPPLIED_METADATA_BYTES = 4096
_STRICT = ConfigDict(extra="forbid", strict=True, frozen=True)


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must be nonblank")
    return value


BoundedIdentifier = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=128), AfterValidator(_nonblank)
]
Reason = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=2000), AfterValidator(_nonblank)
]


def normalize_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    if not normalized.strip() or normalized in {".", ".."}:
        raise UnsafeFilename("filename must be a nonblank basename")
    if len(normalized.encode("utf-8")) > 255:
        raise UnsafeFilename("filename exceeds 255 UTF-8 bytes")
    if any(unicodedata.category(ch) in {"Cc", "Cf", "Cs"} for ch in normalized):
        raise UnsafeFilename("filename contains a control character")
    windows = PureWindowsPath(normalized)
    if (
        "/" in normalized
        or "\\" in normalized
        or PurePosixPath(normalized).is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or normalized.casefold().startswith("\\\\?\\")
    ):
        raise UnsafeFilename("filename must not contain a path")
    return normalized


class SuppliedImageMetadata(BaseModel):
    model_config = _STRICT
    width_px: int = Field(strict=True, gt=0, le=MAX_IMAGE_DIMENSION_PX)
    height_px: int = Field(strict=True, gt=0, le=MAX_IMAGE_DIMENSION_PX)


class SuppliedVideoMetadata(BaseModel):
    model_config = _STRICT
    width_px: int = Field(strict=True, gt=0, le=MAX_VIDEO_DIMENSION_PX)
    height_px: int = Field(strict=True, gt=0, le=MAX_VIDEO_DIMENSION_PX)
    duration_ms: int = Field(strict=True, gt=0, le=MAX_VIDEO_DURATION_MS)


class UploadMetadata(BaseModel):
    model_config = _STRICT
    image: SuppliedImageMetadata | None = None
    video: SuppliedVideoMetadata | None = None

    @model_validator(mode="after")
    def _exclusive_and_bounded(self) -> UploadMetadata:
        if self.image is not None and self.video is not None:
            raise ValueError("only one supplied metadata family is permitted")
        encoded = json.dumps(
            self.model_dump(mode="json", exclude_none=True), separators=(",", ":"), sort_keys=True
        ).encode()
        if len(encoded) > MAX_SUPPLIED_METADATA_BYTES:
            raise ValueError("supplied metadata exceeds 4096 bytes")
        return self


class FileTypeValidation(BaseModel):
    model_config = _STRICT
    kind: EvidenceKind
    canonical_media_type: str
    normalized_filename: str

    @model_validator(mode="after")
    def _kind_matches_media_type(self) -> FileTypeValidation:
        expected = {
            "image/png": EvidenceKind.IMAGE,
            "image/jpeg": EvidenceKind.IMAGE,
            "video/mp4": EvidenceKind.VIDEO,
            "text/plain": EvidenceKind.TEXT,
        }
        if expected.get(self.canonical_media_type) is not self.kind:
            raise ValueError("evidence kind does not match canonical media type")
        return self


class UploadEvidenceCommand(BaseModel):
    model_config = _STRICT
    matter_id: UUID
    caller_filename: str
    declared_media_type: str
    expected_byte_size: int = Field(strict=True, gt=0, le=MAX_EVIDENCE_BYTES)
    actor: ActorRef
    source_channel: BoundedIdentifier
    supplied_metadata: UploadMetadata | None = None
    correlation_id: UUID | None = None

    @field_validator("caller_filename")
    @classmethod
    def _safe_filename(cls, value: str) -> str:
        return normalize_filename(value)

    @model_validator(mode="after")
    def _metadata_matches_declared_family(self) -> UploadEvidenceCommand:
        if self.supplied_metadata is None:
            return self
        image = self.supplied_metadata.image
        video = self.supplied_metadata.video
        if self.declared_media_type in {"image/png", "image/jpeg"}:
            if video is not None:
                raise ValueError("image upload cannot contain video metadata")
        elif self.declared_media_type == "video/mp4":
            if image is not None:
                raise ValueError("video upload cannot contain image metadata")
        elif image is not None or video is not None:
            raise ValueError("text or unsupported uploads cannot contain media metadata")
        return self


class RegisterDerivedEvidenceCommand(UploadEvidenceCommand):
    source_evidence_id: UUID
    operation_code: BoundedIdentifier
    operation_version: BoundedIdentifier
    processor_version: BoundedIdentifier
    parameters_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    deterministic: bool = Field(strict=True)


class ReviewEvidenceCommand(BaseModel):
    model_config = _STRICT
    matter_id: UUID
    evidence_id: UUID
    expected_row_version: int = Field(strict=True, ge=1)
    target_status: EvidenceReviewStatus
    reviewer: ActorRef
    reviewed_at: datetime
    reason: Reason
    source_channel: BoundedIdentifier
    correlation_id: UUID | None = None

    @field_validator("reviewed_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        return value

    @field_validator("target_status")
    @classmethod
    def _terminal(cls, value: EvidenceReviewStatus) -> EvidenceReviewStatus:
        if value is EvidenceReviewStatus.UPLOADED:
            raise ValueError("review target must be terminal")
        return value


class LinkEvidenceChecklistCommand(BaseModel):
    model_config = _STRICT
    matter_id: UUID
    evidence_id: UUID
    checklist_item_id: BoundedIdentifier
    actor: ActorRef
    linked_at: datetime
    source_channel: BoundedIdentifier
    correlation_id: UUID | None = None

    @field_validator("linked_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("linked_at must be timezone-aware")
        return value


class ReadEvidenceCommand(BaseModel):
    model_config = _STRICT
    matter_id: UUID
    evidence_id: UUID | None = None
    actor: ActorRef
    source_channel: BoundedIdentifier
    correlation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: UUID
    matter_id: UUID
    artifact_sha256: str
    evidence_kind: EvidenceKind
    evidence_role: EvidenceRole
    caller_filename: str
    declared_media_type: str
    detected_media_type: str
    expected_byte_size: int
    supplied_unverified_metadata: dict[str, object]
    review_status: EvidenceReviewStatus
    row_version: int
    registered_by: str
    registered_at: datetime
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_reason: str | None


@dataclass(frozen=True, slots=True)
class EvidenceDerivation:
    derivation_id: UUID
    matter_id: UUID
    source_evidence_id: UUID
    source_artifact_sha256: str
    derived_evidence_id: UUID
    derived_artifact_sha256: str
    operation_code: str
    operation_version: str
    processor_version: str
    parameters_sha256: str | None
    deterministic: bool
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvidenceChecklistLink:
    matter_id: UUID
    evidence_id: UUID
    playbook_version_id: UUID
    checklist_item_id: str
    linked_by: str
    linked_at: datetime

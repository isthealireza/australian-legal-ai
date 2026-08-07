from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from legal_ai.evidence.errors import UnsafeFilename
from legal_ai.evidence.models import (
    MAX_IMAGE_DIMENSION_PX,
    MAX_VIDEO_DURATION_MS,
    ReviewEvidenceCommand,
    SuppliedImageMetadata,
    SuppliedVideoMetadata,
    UploadEvidenceCommand,
    normalize_filename,
)
from legal_ai.evidence.types import EvidenceReviewStatus


@pytest.mark.parametrize(
    "filename",
    [
        "",
        " ",
        ".",
        "..",
        "a/b.png",
        "a\\b.png",
        "/a.png",
        "C:a.png",
        "C:\\a.png",
        "\\\\server\\a.png",
        "\\\\?\\C:\\a.png",
        "a\x00.png",
        "a\x1f.png",
        "a\u202e.png",
    ],
)
def test_unsafe_filenames_are_rejected(filename: str) -> None:
    with pytest.raises(UnsafeFilename):
        normalize_filename(filename)


def test_filename_normalizes_nfc_and_preserves_spelling() -> None:
    assert normalize_filename("Cafe\u0301.PNG") == "Café.PNG"


def test_filename_utf8_boundary() -> None:
    assert normalize_filename("a" * 251 + ".txt")
    with pytest.raises(UnsafeFilename):
        normalize_filename("é" * 126 + ".txt")


def test_upload_command_is_strict_and_forbids_authoritative_fields() -> None:
    valid = dict(
        matter_id=uuid4(),
        caller_filename="x.txt",
        declared_media_type="text/plain",
        expected_byte_size=1,
        actor="operator",
        source_channel="test",
    )
    with pytest.raises(ValidationError):
        UploadEvidenceCommand.model_validate({**valid, "expected_byte_size": True})
    with pytest.raises(ValidationError):
        UploadEvidenceCommand.model_validate({**valid, "storage_key": "caller"})


def test_supplied_metadata_boundaries() -> None:
    SuppliedImageMetadata(width_px=MAX_IMAGE_DIMENSION_PX, height_px=1)
    SuppliedVideoMetadata(width_px=1, height_px=1, duration_ms=MAX_VIDEO_DURATION_MS)
    with pytest.raises(ValidationError):
        SuppliedImageMetadata(width_px=MAX_IMAGE_DIMENSION_PX + 1, height_px=1)
    with pytest.raises(ValidationError):
        SuppliedVideoMetadata(width_px=1, height_px=1, duration_ms=0)


def test_review_requires_terminal_state_and_aware_time() -> None:
    values = dict(
        matter_id=uuid4(),
        evidence_id=uuid4(),
        expected_row_version=1,
        reviewer="reviewer",
        reviewed_at=datetime.now(UTC),
        reason="checked",
        source_channel="test",
    )
    ReviewEvidenceCommand.model_validate(
        {**values, "target_status": EvidenceReviewStatus.REVIEW_ACCEPTED}
    )
    with pytest.raises(ValidationError):
        ReviewEvidenceCommand.model_validate(
            {**values, "target_status": EvidenceReviewStatus.UPLOADED}
        )
    with pytest.raises(ValidationError):
        ReviewEvidenceCommand.model_validate(
            {
                **values,
                "reviewed_at": datetime.now(),
                "target_status": EvidenceReviewStatus.REVIEW_REJECTED,
            }
        )

"""Bounded streaming file-family validation for evidence uploads."""

import codecs
from collections.abc import Callable, Iterable, Iterator
from pathlib import PurePath
from typing import cast

from legal_ai.provenance.content_store import ArtifactContent

from .errors import (
    DeclaredMediaTypeMismatch,
    EmptyEvidenceInput,
    EvidenceSizeLimitExceeded,
    ExpectedSizeMismatch,
    ExtensionMismatch,
    MalformedSignature,
    TruncatedEvidenceStream,
    UnsupportedFileType,
)
from .models import MAX_EVIDENCE_BYTES, FileTypeValidation, normalize_filename
from .types import EvidenceKind

_READ_SIZE = 64 * 1024
_PREFIX_LIMIT = 4096
_TYPE_RULES = {
    "image/png": (EvidenceKind.IMAGE, frozenset({".png"})),
    "image/jpeg": (EvidenceKind.IMAGE, frozenset({".jpg", ".jpeg"})),
    "video/mp4": (EvidenceKind.VIDEO, frozenset({".mp4"})),
    "text/plain": (EvidenceKind.TEXT, frozenset({".txt"})),
}


class ValidatedEvidenceStream:
    """One-shot iterable that validates while yielding bounded chunks."""

    def __init__(
        self,
        content: ArtifactContent,
        *,
        filename: str,
        declared_media_type: str,
        expected_byte_size: int,
    ) -> None:
        self._content = content
        self._filename = normalize_filename(filename)
        self._declared = declared_media_type
        self._expected = expected_byte_size
        self.result: FileTypeValidation | None = None

    def __iter__(self) -> Iterator[bytes]:
        if self._declared not in _TYPE_RULES:
            raise UnsupportedFileType("declared media type is not allowed")
        if self._expected <= 0 or self._expected > MAX_EVIDENCE_BYTES:
            raise EvidenceSizeLimitExceeded("expected size is outside the upload boundary")
        prefix = bytearray()
        suffix = bytearray()
        total = 0
        decoder = (
            codecs.getincrementaldecoder("utf-8")("strict")
            if self._declared == "text/plain"
            else None
        )
        try:
            for chunk in self._chunks():
                if not isinstance(chunk, bytes):
                    raise TruncatedEvidenceStream("stream returned a non-bytes chunk")
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_EVIDENCE_BYTES:
                    raise EvidenceSizeLimitExceeded("evidence exceeds 100 MiB")
                if total > self._expected:
                    raise ExpectedSizeMismatch("stream exceeded expected size")
                if len(prefix) < _PREFIX_LIMIT:
                    prefix.extend(chunk[: _PREFIX_LIMIT - len(prefix)])
                suffix.extend(chunk)
                del suffix[:-2]
                if decoder is not None:
                    try:
                        decoder.decode(chunk, final=False)
                    except UnicodeDecodeError as exc:
                        raise MalformedSignature("text is not strict UTF-8") from exc
                yield chunk
        except (
            EmptyEvidenceInput,
            EvidenceSizeLimitExceeded,
            ExpectedSizeMismatch,
            MalformedSignature,
            TruncatedEvidenceStream,
        ):
            raise
        except Exception as exc:
            raise TruncatedEvidenceStream("evidence stream was interrupted") from exc
        if total == 0:
            raise EmptyEvidenceInput("empty evidence is not permitted")
        if total != self._expected:
            raise ExpectedSizeMismatch("stream contained fewer bytes than expected")
        if decoder is not None:
            try:
                decoder.decode(b"", final=True)
            except UnicodeDecodeError as exc:
                raise MalformedSignature("text ended with incomplete UTF-8") from exc
        self.result = validate_file_type(
            prefix=bytes(prefix),
            suffix=bytes(suffix),
            filename=self._filename,
            declared_media_type=self._declared,
        )

    def _chunks(self) -> Iterator[object]:
        reader = getattr(self._content, "read", None)
        if callable(reader):
            read = cast(Callable[[int], object], reader)
            while True:
                chunk = read(_READ_SIZE)
                if chunk == b"":
                    return
                yield chunk
        else:
            yield from cast(Iterable[object], self._content)


def validate_file_type(
    *, prefix: bytes, suffix: bytes, filename: str, declared_media_type: str
) -> FileTypeValidation:
    """Validate the exact allowlisted family using only bounded leading/trailing data."""

    detected: str
    if (
        len(prefix) >= 33
        and prefix.startswith(b"\x89PNG\r\n\x1a\n")
        and prefix[12:16] == b"IHDR"
        and int.from_bytes(prefix[8:12], "big") == 13
        and int.from_bytes(prefix[16:20], "big") > 0
        and int.from_bytes(prefix[20:24], "big") > 0
        and prefix[26] == 0
        and prefix[27] == 0
        and prefix[28] in {0, 1}
    ):
        detected = "image/png"
    elif prefix.startswith(b"\xff\xd8") and suffix == b"\xff\xd9":
        detected = "image/jpeg"
    elif _has_valid_ftyp(prefix):
        detected = "video/mp4"
    elif declared_media_type == "text/plain":
        detected = "text/plain"
    else:
        raise MalformedSignature("file signature is malformed or unsupported")
    if declared_media_type not in _TYPE_RULES:
        raise UnsupportedFileType("declared media type is not allowed")
    if detected != declared_media_type:
        raise DeclaredMediaTypeMismatch("declared and detected media types differ")
    kind, extensions = _TYPE_RULES[detected]
    extension = PurePath(filename).suffix.casefold()
    if extension not in extensions:
        raise ExtensionMismatch("filename extension does not match detected media type")
    return FileTypeValidation(
        kind=kind, canonical_media_type=detected, normalized_filename=filename
    )


def _has_valid_ftyp(prefix: bytes) -> bool:
    offset = 0
    while offset + 8 <= len(prefix):
        size = int.from_bytes(prefix[offset : offset + 4], "big")
        box_type = prefix[offset + 4 : offset + 8]
        if size == 1:
            if offset + 16 > len(prefix):
                return False
            size = int.from_bytes(prefix[offset + 8 : offset + 16], "big")
            minimum = 16
        else:
            minimum = 8
        if size < minimum or offset + size > len(prefix):
            return False
        if box_type == b"ftyp":
            return size >= minimum + 8
        offset += size
    return False

"""Synchronous local content-addressed artifact storage."""

import hashlib
import ntpath
import os
import posixpath
import tempfile
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from .errors import (
    ArtifactIntegrityError,
    ArtifactPathError,
    ArtifactPublicationError,
    ArtifactValidationError,
)
from .models import validate_sha256

_READ_CHUNK_SIZE = 64 * 1024
_WINDOWS_RETRY_ATTEMPTS = 3
_WINDOWS_RETRY_BACKOFF_SECONDS = 0.01
_WINDOWS_TRANSIENT_WINERRORS = frozenset({5, 32, 33})


def _normalize_path_for_comparison(path: str, *, windows: bool) -> str:
    if windows:
        normalized = path.replace("/", "\\")
        casefolded = normalized.casefold()
        if casefolded.startswith("\\\\?\\unc\\"):
            normalized = "\\\\" + normalized[8:]
        elif casefolded.startswith("\\\\?\\"):
            normalized = normalized[4:]
        return ntpath.normcase(ntpath.normpath(normalized))
    return posixpath.normcase(posixpath.normpath(path))


def _is_path_within_root(root: str, candidate: str, *, windows: bool) -> bool:
    path_module = ntpath if windows else posixpath
    normalized_root = _normalize_path_for_comparison(root, windows=windows)
    normalized_candidate = _normalize_path_for_comparison(candidate, windows=windows)
    if not path_module.isabs(normalized_root) or not path_module.isabs(normalized_candidate):
        return False
    try:
        return bool(
            path_module.commonpath((normalized_root, normalized_candidate)) == normalized_root
        )
    except ValueError:
        return False


class BinaryReader(Protocol):
    """Minimal binary stream interface accepted by the artifact store."""

    def read(self, size: int = -1, /) -> bytes:
        """Read at most ``size`` bytes."""


ArtifactContent = Iterable[bytes] | BinaryReader


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    """Verified local result of one content-addressed publication."""

    sha256: str
    byte_size: int
    storage_key: str
    path: Path


class LocalArtifactStore:
    """Publish immutable blobs beneath an injected filesystem root."""

    def __init__(self, root: Path) -> None:
        configured_root = Path(root)
        try:
            configured_root.mkdir(parents=True, exist_ok=True)
            self._root = configured_root.resolve(strict=True)
        except OSError as exc:
            raise ArtifactPathError("artifact root could not be initialized safely") from exc

    def store(
        self,
        content: ArtifactContent,
        *,
        max_bytes: int,
        expected_sha256: str | None = None,
    ) -> StoredArtifact:
        """Stream, hash, and publish one blob without overwriting a final path."""

        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ArtifactValidationError("maximum byte limit must be a positive integer")
        if expected_sha256 is not None:
            try:
                validate_sha256(expected_sha256)
            except ValueError as exc:
                raise ArtifactValidationError("expected SHA-256 is malformed") from exc

        temporary_path: Path | None = None
        publication_verified = False
        digest = hashlib.sha256()
        byte_size = 0
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".artifact-",
                suffix=".tmp",
                dir=self._root,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                for chunk in self._iter_chunks(content):
                    if not isinstance(chunk, bytes):
                        raise ArtifactValidationError("artifact chunks must be bytes")
                    if not chunk:
                        continue
                    byte_size += len(chunk)
                    if byte_size > max_bytes:
                        raise ArtifactValidationError("artifact exceeded the maximum byte limit")
                    digest.update(chunk)
                    temporary_file.write(chunk)
                if byte_size == 0:
                    raise ArtifactValidationError("empty artifacts are not permitted")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            actual_sha256 = digest.hexdigest()
            if expected_sha256 is not None and actual_sha256 != expected_sha256:
                raise ArtifactValidationError("artifact SHA-256 did not match the expected value")

            storage_key_path = self._storage_key_for_sha256(actual_sha256)
            final_path = self._validated_final_path(storage_key_path, actual_sha256)
            self._prepare_storage_directories(storage_key_path)

            self._publish(temporary_path, final_path, byte_size, actual_sha256)
            publication_verified = True

            return StoredArtifact(
                sha256=actual_sha256,
                byte_size=byte_size,
                storage_key=storage_key_path.as_posix(),
                path=final_path,
            )
        except OSError as exc:
            raise ArtifactPublicationError("artifact storage operation failed") from exc
        finally:
            if temporary_path is not None:
                self._cleanup_temporary(
                    temporary_path,
                    publication_verified=publication_verified,
                )

    @staticmethod
    def _iter_chunks(content: ArtifactContent) -> Iterator[object]:
        reader = getattr(content, "read", None)
        if callable(reader):
            read = cast(Callable[[int], object], reader)
            while True:
                chunk = read(_READ_CHUNK_SIZE)
                if chunk == b"":
                    return
                yield chunk
        else:
            try:
                yield from cast(Iterable[object], content)
            except TypeError as exc:
                raise ArtifactValidationError(
                    "artifact content must be a binary stream or iterable of bytes"
                ) from exc

    def _storage_key_for_sha256(self, sha256: str) -> Path:
        try:
            validate_sha256(sha256)
        except ValueError as exc:
            raise ArtifactPathError("artifact storage key used an invalid SHA-256") from exc
        return Path("sha256", sha256[:2], sha256[2:4], f"{sha256}.blob")

    def _validated_final_path(self, storage_key: Path, sha256: str) -> Path:
        expected_parts = (
            "sha256",
            sha256[:2],
            sha256[2:4],
            f"{sha256}.blob",
        )
        if (
            storage_key.is_absolute()
            or any(part in {"", ".", ".."} for part in storage_key.parts)
            or storage_key.parts != expected_parts
        ):
            raise ArtifactPathError(
                "derived artifact storage key was not the approved relative key"
            )

        final_path = self._root.joinpath(*storage_key.parts)
        if not _is_path_within_root(
            str(self._root),
            str(final_path),
            windows=os.name == "nt",
        ):
            raise ArtifactPathError("derived artifact path is outside the configured root")
        return final_path

    def _prepare_storage_directories(self, storage_key: Path) -> None:
        current = self._root
        for component in storage_key.parts[:-1]:
            current /= component
            current.mkdir(exist_ok=True)
            if current.is_symlink() or current.is_junction() or not current.is_dir():
                raise ArtifactPathError(
                    "artifact storage directory was not a regular directory beneath the root"
                )

    def _publish(
        self,
        temporary_path: Path,
        final_path: Path,
        expected_size: int,
        expected_sha256: str,
    ) -> None:
        for attempt in range(_WINDOWS_RETRY_ATTEMPTS):
            try:
                os.link(temporary_path, final_path)
            except OSError as exc:
                if self._destination_exists(final_path):
                    self._verify_existing(final_path, expected_size, expected_sha256)
                    return
                if self._is_transient_windows_error(exc) and attempt + 1 < (
                    _WINDOWS_RETRY_ATTEMPTS
                ):
                    time.sleep(_WINDOWS_RETRY_BACKOFF_SECONDS)
                    continue
                raise ArtifactPublicationError("artifact publication failed") from exc
            else:
                self._verify_existing(final_path, expected_size, expected_sha256)
                return

    @staticmethod
    def _destination_exists(path: Path) -> bool:
        try:
            path.lstat()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise ArtifactPublicationError(
                "artifact destination existence could not be determined"
            ) from exc
        return True

    @staticmethod
    def _is_transient_windows_error(error: OSError) -> bool:
        winerror = getattr(error, "winerror", None)
        return winerror in _WINDOWS_TRANSIENT_WINERRORS

    def _cleanup_temporary(self, path: Path, *, publication_verified: bool) -> None:
        last_error: OSError | None = None
        for attempt in range(_WINDOWS_RETRY_ATTEMPTS):
            try:
                path.unlink(missing_ok=True)
            except FileNotFoundError:
                return
            except OSError as exc:
                last_error = exc
                if self._is_transient_windows_error(exc) and attempt + 1 < (
                    _WINDOWS_RETRY_ATTEMPTS
                ):
                    time.sleep(_WINDOWS_RETRY_BACKOFF_SECONDS)
                    continue
                break
            else:
                return

        if publication_verified:
            return
        raise ArtifactPublicationError(
            "temporary artifact cleanup failed before publication"
        ) from last_error

    def _verify_existing(
        self,
        path: Path,
        expected_size: int,
        expected_sha256: str,
    ) -> None:
        if not _is_path_within_root(str(self._root), str(path), windows=os.name == "nt"):
            raise ArtifactPathError("existing artifact path is outside the configured root")
        if path.is_symlink() or not path.is_file():
            raise ArtifactIntegrityError("existing artifact is not a regular file")

        digest = hashlib.sha256()
        byte_size = 0
        try:
            with path.open("rb") as existing:
                while chunk := existing.read(_READ_CHUNK_SIZE):
                    byte_size += len(chunk)
                    digest.update(chunk)
        except OSError as exc:
            raise ArtifactIntegrityError("existing artifact could not be verified") from exc
        if byte_size != expected_size or digest.hexdigest() != expected_sha256:
            raise ArtifactIntegrityError("existing artifact size or SHA-256 did not match")

import errno
import hashlib
import io
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, BrokenBarrierError, Lock

import pytest

from legal_ai.provenance import (
    ArtifactIntegrityError,
    ArtifactPathError,
    ArtifactPublicationError,
    ArtifactValidationError,
    LocalArtifactStore,
    StoredArtifact,
)
from legal_ai.provenance.content_store import _is_path_within_root


class _SimulatedWindowsPermissionError(PermissionError):
    winerror: int

    def __init__(self, winerror: int, message: str) -> None:
        super().__init__(errno.EACCES, message)
        self.winerror = winerror


def _temporary_files(root: Path) -> list[Path]:
    return list(root.rglob(".artifact-*.tmp"))


def test_store_streams_bytes_and_calculates_sha256(tmp_path: Path) -> None:
    chunks_yielded = 0

    def chunks() -> Iterator[bytes]:
        nonlocal chunks_yielded
        for chunk in (b"immutable ", b"official ", b"bytes"):
            chunks_yielded += 1
            yield chunk

    store = LocalArtifactStore(tmp_path)
    artifact = store.store(chunks(), max_bytes=24)

    expected = b"immutable official bytes"
    assert chunks_yielded == 3
    assert artifact.sha256 == hashlib.sha256(expected).hexdigest()
    assert artifact.byte_size == len(expected)
    assert artifact.path.read_bytes() == expected


def test_storage_key_is_derived_only_from_lowercase_sha256(tmp_path: Path) -> None:
    artifact = LocalArtifactStore(tmp_path).store([b"artifact"], max_bytes=8)

    assert artifact.storage_key == (
        f"sha256/{artifact.sha256[:2]}/{artifact.sha256[2:4]}/{artifact.sha256}.blob"
    )
    assert artifact.path == tmp_path.resolve() / Path(artifact.storage_key)


def test_exactly_at_limit_succeeds_for_binary_stream(tmp_path: Path) -> None:
    artifact = LocalArtifactStore(tmp_path).store(io.BytesIO(b"12345"), max_bytes=5)

    assert artifact.byte_size == 5


def test_one_byte_over_limit_fails_and_publishes_nothing(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)

    with pytest.raises(ArtifactValidationError, match="maximum byte limit"):
        store.store([b"123", b"456"], max_bytes=5)

    assert list(tmp_path.rglob("*.blob")) == []


@pytest.mark.parametrize("chunks", [[], [b""], io.BytesIO(b"")])
def test_empty_artifact_fails(tmp_path: Path, chunks: object) -> None:
    store = LocalArtifactStore(tmp_path)

    with pytest.raises(ArtifactValidationError, match="empty"):
        store.store(chunks, max_bytes=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_chunk", ["text", bytearray(b"bytes"), 1])
def test_non_byte_chunk_fails(tmp_path: Path, bad_chunk: object) -> None:
    store = LocalArtifactStore(tmp_path)

    with pytest.raises(ArtifactValidationError, match="bytes"):
        store.store([b"valid", bad_chunk], max_bytes=100)  # type: ignore[list-item]


def test_expected_hash_mismatch_fails(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)

    with pytest.raises(ArtifactValidationError, match="did not match"):
        store.store([b"actual"], max_bytes=6, expected_sha256="0" * 64)


@pytest.mark.parametrize(
    "malformed_hash",
    ["", "a" * 63, "A" * 64, "g" * 64, "sha256:" + ("a" * 64)],
)
def test_malformed_expected_hash_fails(tmp_path: Path, malformed_hash: str) -> None:
    store = LocalArtifactStore(tmp_path)

    with pytest.raises(ArtifactValidationError, match="malformed"):
        store.store([b"actual"], max_bytes=6, expected_sha256=malformed_hash)


def test_existing_identical_artifact_is_verified_and_reused(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    first = store.store([b"same bytes"], max_bytes=10)
    second = store.store([b"same ", b"bytes"], max_bytes=10)

    assert second == first
    assert first.path.read_bytes() == b"same bytes"


def test_non_file_exists_publication_error_reuses_identical_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalArtifactStore(tmp_path)
    first = store.store([b"same bytes"], max_bytes=10)

    def fail_publication(_source: object, _destination: object) -> None:
        raise PermissionError(errno.EACCES, "simulated Windows sharing failure")

    monkeypatch.setattr(os, "link", fail_publication)

    assert store.store([b"same bytes"], max_bytes=10) == first


def test_publication_error_without_final_is_typed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_publication(_source: object, _destination: object) -> None:
        raise OSError(errno.EIO, "simulated publication failure")

    monkeypatch.setattr(os, "link", fail_publication)

    with pytest.raises(ArtifactPublicationError, match="publication failed") as caught:
        LocalArtifactStore(tmp_path).store([b"content"], max_bytes=7)

    assert isinstance(caught.value.__cause__, OSError)
    assert list(tmp_path.rglob("*.blob")) == []
    assert _temporary_files(tmp_path) == []


def test_storage_os_error_never_escapes_raw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalArtifactStore(tmp_path)

    def deny_directory_creation(
        _path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        del mode, parents, exist_ok
        raise PermissionError(errno.EACCES, "simulated directory failure")

    monkeypatch.setattr(Path, "mkdir", deny_directory_creation)

    with pytest.raises(ArtifactPublicationError, match="storage operation failed") as caught:
        store.store([b"content"], max_bytes=7)

    assert isinstance(caught.value.__cause__, PermissionError)
    assert _temporary_files(tmp_path) == []


def test_transient_windows_publication_error_is_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_link = os.link
    publication_attempts = 0

    def transient_then_publish(source: Path, destination: Path) -> None:
        nonlocal publication_attempts
        publication_attempts += 1
        if publication_attempts < 3:
            raise _SimulatedWindowsPermissionError(
                32,
                "simulated Windows sharing violation",
            )
        original_link(source, destination)

    monkeypatch.setattr(os, "link", transient_then_publish)

    artifact = LocalArtifactStore(tmp_path).store([b"content"], max_bytes=7)

    assert publication_attempts == 3
    assert artifact.path.read_bytes() == b"content"
    assert _temporary_files(tmp_path) == []


def test_non_allowlisted_windows_permission_error_is_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication_attempts = 0

    def deny_publication(_source: Path, _destination: Path) -> None:
        nonlocal publication_attempts
        publication_attempts += 1
        raise _SimulatedWindowsPermissionError(
            87,
            "simulated non-transient permission error",
        )

    monkeypatch.setattr(os, "link", deny_publication)

    with pytest.raises(ArtifactPublicationError, match="publication failed"):
        LocalArtifactStore(tmp_path).store([b"content"], max_bytes=7)

    assert publication_attempts == 1
    assert list(tmp_path.rglob("*.blob")) == []
    assert _temporary_files(tmp_path) == []


def test_publication_race_with_corrupt_final_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalArtifactStore(tmp_path)
    artifact = store.store([b"original"], max_bytes=8)
    artifact.path.write_bytes(b"tampered")

    def fail_publication(_source: object, _destination: object) -> None:
        raise PermissionError(errno.EACCES, "simulated Windows sharing failure")

    monkeypatch.setattr(os, "link", fail_publication)

    with pytest.raises(ArtifactIntegrityError, match="existing artifact"):
        store.store([b"original"], max_bytes=8)

    assert artifact.path.read_bytes() == b"tampered"


def test_concurrent_identical_publication_is_windows_safe(tmp_path: Path) -> None:
    worker_count = 8
    publications_per_worker = 16
    content = b"concurrent immutable artifact"
    expected_sha256 = hashlib.sha256(content).hexdigest()
    expected_key = f"sha256/{expected_sha256[:2]}/{expected_sha256[2:4]}/{expected_sha256}.blob"
    barrier = Barrier(worker_count)
    error_lock = Lock()
    errors: list[BaseException] = []
    store = LocalArtifactStore(tmp_path)

    def publish_repeatedly(_worker: int) -> list[StoredArtifact]:
        results: list[StoredArtifact] = []
        try:
            for _iteration in range(publications_per_worker):
                barrier.wait(timeout=5)
                results.append(store.store([content], max_bytes=len(content)))
        except BrokenBarrierError:
            pass
        except BaseException as exc:
            with error_lock:
                errors.append(exc)
            barrier.abort()
        return results

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        worker_results = list(executor.map(publish_repeatedly, range(worker_count)))

    assert errors == []
    artifacts = [artifact for results in worker_results for artifact in results]
    assert len(artifacts) == worker_count * publications_per_worker
    assert {artifact.sha256 for artifact in artifacts} == {expected_sha256}
    assert {artifact.byte_size for artifact in artifacts} == {len(content)}
    assert {artifact.storage_key for artifact in artifacts} == {expected_key}
    final_blobs = list(tmp_path.rglob("*.blob"))
    assert len(final_blobs) == 1
    assert final_blobs[0].read_bytes() == content
    assert hashlib.sha256(final_blobs[0].read_bytes()).hexdigest() == expected_sha256
    assert _temporary_files(tmp_path) == []


def test_existing_corrupt_artifact_fails_closed(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    artifact = store.store([b"original"], max_bytes=8)
    artifact.path.write_bytes(b"corrupt!")

    with pytest.raises(ArtifactIntegrityError, match="existing artifact"):
        store.store([b"original"], max_bytes=8)


def test_existing_final_artifact_is_never_overwritten(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    artifact = store.store([b"original"], max_bytes=8)
    artifact.path.write_bytes(b"tampered")

    with pytest.raises(ArtifactIntegrityError):
        store.store([b"original"], max_bytes=8)

    assert artifact.path.read_bytes() == b"tampered"


def test_temporary_file_is_removed_after_success(tmp_path: Path) -> None:
    LocalArtifactStore(tmp_path).store([b"success"], max_bytes=7)

    assert _temporary_files(tmp_path) == []


def test_temporary_file_is_removed_after_handled_failure(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)

    with pytest.raises(ArtifactValidationError):
        store.store([b"too", b"large"], max_bytes=3)

    assert _temporary_files(tmp_path) == []


def test_cleanup_permission_error_after_verified_publication_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_unlink = Path.unlink
    cleanup_attempts = 0

    def deny_temporary_cleanup(path: Path, *, missing_ok: bool = False) -> None:
        nonlocal cleanup_attempts
        if path.name.startswith(".artifact-"):
            cleanup_attempts += 1
            raise _SimulatedWindowsPermissionError(
                32,
                "simulated Windows sharing violation",
            )
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", deny_temporary_cleanup)

    artifact = LocalArtifactStore(tmp_path).store([b"published"], max_bytes=9)

    assert artifact.path.read_bytes() == b"published"
    assert cleanup_attempts == 3
    assert len(_temporary_files(tmp_path)) == 1


def test_cleanup_error_before_publication_remains_typed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_publication(_source: object, _destination: object) -> None:
        raise OSError(errno.EIO, "simulated publication failure")

    def deny_cleanup(_path: Path, *, missing_ok: bool = False) -> None:
        del missing_ok
        raise PermissionError(errno.EACCES, "simulated cleanup failure")

    monkeypatch.setattr(os, "link", fail_publication)
    monkeypatch.setattr(Path, "unlink", deny_cleanup)

    with pytest.raises(ArtifactPublicationError, match="cleanup failed") as caught:
        LocalArtifactStore(tmp_path).store([b"content"], max_bytes=7)

    assert isinstance(caught.value.__cause__, PermissionError)


def test_caller_filename_cannot_affect_storage_path(tmp_path: Path) -> None:
    class NamedStream(io.BytesIO):
        name = "../../caller-controlled.pdf"

    artifact = LocalArtifactStore(tmp_path).store(NamedStream(b"content"), max_bytes=7)

    assert artifact.storage_key.startswith("sha256/")
    assert "caller-controlled" not in artifact.storage_key
    assert artifact.path.is_relative_to(tmp_path.resolve())


def test_path_escape_is_rejected_before_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outside = tmp_path.parent / "escaped.blob"
    store = LocalArtifactStore(tmp_path)
    monkeypatch.setattr(
        store,
        "_storage_key_for_sha256",
        lambda _sha256: Path("..") / outside.name,
    )

    with pytest.raises(ArtifactPathError, match="approved relative key"):
        store.store([b"content"], max_bytes=7)

    assert not outside.exists()
    assert _temporary_files(tmp_path) == []


def test_windows_extended_paths_are_compared_case_insensitively() -> None:
    root = r"C:\ArtifactVault"

    assert _is_path_within_root(
        root,
        r"\\?\c:\artifactvault\sha256\ab\cd\digest.blob",
        windows=True,
    )
    assert not _is_path_within_root(
        root,
        r"\\?\C:\ArtifactVault\..\escaped\digest.blob",
        windows=True,
    )
    assert not _is_path_within_root(
        root,
        r"\\?\D:\ArtifactVault\sha256\ab\cd\digest.blob",
        windows=True,
    )


def test_storage_directory_junction_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalArtifactStore(tmp_path)
    monkeypatch.setattr(Path, "is_junction", lambda path: path.name == "sha256")

    with pytest.raises(ArtifactPathError, match="regular directory"):
        store.store([b"content"], max_bytes=7)

    assert list(tmp_path.rglob("*.blob")) == []
    assert _temporary_files(tmp_path) == []

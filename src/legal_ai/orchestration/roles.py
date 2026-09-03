"""Worker role configuration.

Write access is denied by default. A role becomes able to change files only
when its configuration is `SCOPED_WRITE` *and* the exact repository-relative
path appears in an explicit allowlist. There are no globs, no prefixes and no
implicit widening: an unlisted path is refused.

`normalise_repo_path` is a pure function over the *name*. It rejects every
spelling that a case-insensitive or name-mangling filesystem could treat as
equivalent to a different name — traversal, absolute and drive-qualified paths,
backslashes, non-NFC Unicode, control characters, alternate data streams,
Windows reserved device names, and the trailing dot or space that NTFS strips.

It deliberately does **not** resolve symlinks, because resolution needs
filesystem I/O and would make the check non-deterministic and environment
dependent. Name-level authorisation is not the only barrier: a worker runs in
its own git worktree on its own branch, so it cannot reach the coordinator's
files whatever its allowlist says. See ADR 0016.
"""

from __future__ import annotations

import unicodedata

from pydantic import BaseModel, ConfigDict, model_validator

from legal_ai.orchestration.errors import (
    OrchestrationValidationError,
    RoleAccessDenied,
    UnknownRoleError,
)
from legal_ai.orchestration.types import AccessMode, ExactLine, WorkerRole

_STRICT = ConfigDict(extra="forbid", strict=True, frozen=True)

MAX_WRITABLE_PATHS = 64


_RESERVED_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


def normalise_repo_path(path: str) -> str:
    """Return a canonical repository-relative path, or reject it.

    Rejects every spelling that a filesystem could alias onto a different name.
    Rejection is deliberate: a path is never silently repaired into a canonical
    form, because repairing is what lets an allowlist authorise the wrong file.
    """

    if not path.strip():
        raise OrchestrationValidationError("path must contain a non-whitespace character")
    if unicodedata.normalize("NFC", path) != path:
        raise OrchestrationValidationError(f"path must be Unicode NFC: {path!r}")
    if any(character < " " or character == "" for character in path):
        raise OrchestrationValidationError(f"path must not contain control characters: {path!r}")
    if "\\" in path:
        raise OrchestrationValidationError(f"path must use forward slashes: {path!r}")
    if ":" in path:
        raise OrchestrationValidationError(
            f"path must be repository-relative and carry no stream suffix: {path!r}"
        )
    if path.startswith("/"):
        raise OrchestrationValidationError(f"path must be repository-relative: {path!r}")

    segments = [segment for segment in path.split("/") if segment not in {"", "."}]
    if not segments:
        raise OrchestrationValidationError(f"path resolves to nothing: {path!r}")

    for segment in segments:
        if segment == "..":
            raise OrchestrationValidationError(f"path must not traverse upwards: {path!r}")
        if segment != segment.rstrip(". "):
            raise OrchestrationValidationError(
                f"path segment must not end in a dot or space: {path!r}"
            )
        if segment.split(".")[0].upper() in _RESERVED_DEVICE_NAMES:
            raise OrchestrationValidationError(f"path segment is a reserved device name: {path!r}")

    return "/".join(segments)


class RoleConfiguration(BaseModel):
    """What one role is permitted to do in this repository."""

    model_config = _STRICT

    role: WorkerRole
    access_mode: AccessMode
    writable_paths: frozenset[str] = frozenset()
    may_dispatch_workers: bool = False
    may_run_repository_checks: bool = False
    description: ExactLine

    @model_validator(mode="after")
    def _check_access(self) -> RoleConfiguration:
        if self.access_mode is not AccessMode.SCOPED_WRITE and self.writable_paths:
            raise ValueError(
                f"{self.role.value} is {self.access_mode.value} and must declare no writable paths"
            )
        if self.access_mode is AccessMode.SCOPED_WRITE and not self.writable_paths:
            raise ValueError(
                f"{self.role.value} is SCOPED_WRITE and must declare an explicit path allowlist"
            )
        if len(self.writable_paths) > MAX_WRITABLE_PATHS:
            raise ValueError(f"writable path allowlist exceeds {MAX_WRITABLE_PATHS} entries")
        for path in self.writable_paths:
            if normalise_repo_path(path) != path:
                raise ValueError(f"writable path is not canonical: {path!r}")
        return self

    @property
    def may_write(self) -> bool:
        return self.access_mode is AccessMode.SCOPED_WRITE


DEFAULT_ROLE_CONFIGURATIONS: dict[WorkerRole, RoleConfiguration] = {
    WorkerRole.COORDINATOR: RoleConfiguration(
        role=WorkerRole.COORDINATOR,
        access_mode=AccessMode.READ_ONLY,
        may_dispatch_workers=True,
        may_run_repository_checks=True,
        description=(
            "Owns the DAG, integration and implementation decisions. Writes only "
            "through an IMPLEMENTER contract that lists the exact files."
        ),
    ),
    WorkerRole.IMPLEMENTER: RoleConfiguration(
        role=WorkerRole.IMPLEMENTER,
        access_mode=AccessMode.READ_ONLY,
        may_dispatch_workers=False,
        may_run_repository_checks=True,
        description=(
            "Changes files only when a bounded task contract grants SCOPED_WRITE "
            "over a named allowlist; the default configuration grants none."
        ),
    ),
    WorkerRole.REVIEWER: RoleConfiguration(
        role=WorkerRole.REVIEWER,
        access_mode=AccessMode.REVIEW_ONLY,
        may_dispatch_workers=False,
        may_run_repository_checks=True,
        description=(
            "Reads the diff and reports classified findings. Never edits files, "
            "history, branches, tags or Pull Requests."
        ),
    ),
    WorkerRole.EVALUATOR: RoleConfiguration(
        role=WorkerRole.EVALUATOR,
        access_mode=AccessMode.READ_ONLY,
        may_dispatch_workers=False,
        may_run_repository_checks=False,
        description=(
            "Reads code and documents to produce an evaluation memo. Never edits "
            "files and never calls an external provider."
        ),
    ),
}


def resolve_role_configuration(role: WorkerRole) -> RoleConfiguration:
    """Return the default configuration for `role`, or fail closed."""

    configuration = DEFAULT_ROLE_CONFIGURATIONS.get(role)
    if configuration is None:
        raise UnknownRoleError(role=role)
    return configuration


def assert_write_allowed(configuration: RoleConfiguration, path: str) -> None:
    """Raise `RoleAccessDenied` unless `path` is explicitly writable."""

    candidate = normalise_repo_path(path)
    if not configuration.may_write or candidate not in configuration.writable_paths:
        raise RoleAccessDenied(
            role=configuration.role,
            access_mode=configuration.access_mode,
            path=candidate,
        )

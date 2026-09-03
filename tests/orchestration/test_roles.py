"""Role configuration: write access is denied unless explicitly granted."""

from __future__ import annotations

import unicodedata

import pytest
from pydantic import ValidationError

from legal_ai.orchestration.errors import (
    OrchestrationValidationError,
    RoleAccessDenied,
    UnknownRoleError,
)
from legal_ai.orchestration.roles import (
    DEFAULT_ROLE_CONFIGURATIONS,
    RoleConfiguration,
    assert_write_allowed,
    normalise_repo_path,
    resolve_role_configuration,
)
from legal_ai.orchestration.types import AccessMode, WorkerRole


def test_every_role_has_a_default_configuration() -> None:
    for role in WorkerRole:
        assert resolve_role_configuration(role).role is role


def test_no_default_configuration_grants_write_access() -> None:
    for configuration in DEFAULT_ROLE_CONFIGURATIONS.values():
        assert configuration.access_mode is not AccessMode.SCOPED_WRITE
        assert configuration.writable_paths == frozenset()
        assert configuration.may_write is False


def test_only_the_coordinator_may_dispatch_workers() -> None:
    dispatchers = {
        role
        for role, configuration in DEFAULT_ROLE_CONFIGURATIONS.items()
        if configuration.may_dispatch_workers
    }
    assert dispatchers == {WorkerRole.COORDINATOR}


def test_unknown_role_fails_closed() -> None:
    with pytest.raises(UnknownRoleError):
        resolve_role_configuration("ADMIN")  # type: ignore[arg-type]


def test_read_only_role_may_not_declare_writable_paths() -> None:
    with pytest.raises(ValidationError):
        RoleConfiguration(
            role=WorkerRole.REVIEWER,
            access_mode=AccessMode.REVIEW_ONLY,
            writable_paths=frozenset({"src/legal_ai/orchestration/roles.py"}),
            description="reviewer",
        )


def test_scoped_write_requires_a_non_empty_allowlist() -> None:
    with pytest.raises(ValidationError):
        RoleConfiguration(
            role=WorkerRole.IMPLEMENTER,
            access_mode=AccessMode.SCOPED_WRITE,
            description="implementer",
        )


def _scoped(*paths: str) -> RoleConfiguration:
    return RoleConfiguration(
        role=WorkerRole.IMPLEMENTER,
        access_mode=AccessMode.SCOPED_WRITE,
        writable_paths=frozenset(paths),
        description="implementer with a narrow allowlist",
    )


def test_allowlisted_path_is_writable_and_a_sibling_is_not() -> None:
    configuration = _scoped("src/legal_ai/orchestration/roles.py")
    assert_write_allowed(configuration, "src/legal_ai/orchestration/roles.py")
    with pytest.raises(RoleAccessDenied):
        assert_write_allowed(configuration, "src/legal_ai/orchestration/graph.py")


def test_allowlisting_a_file_does_not_allowlist_its_directory() -> None:
    configuration = _scoped("docs/adr/0016-agent-orchestration-foundation.md")
    with pytest.raises(RoleAccessDenied):
        assert_write_allowed(configuration, "docs/adr/0001-product-purpose.md")


def test_traversal_and_absolute_paths_are_refused() -> None:
    configuration = _scoped("src/legal_ai/orchestration/roles.py")
    for path in (
        "src/legal_ai/orchestration/../../../PROJECT_GOVERNANCE.md",
        "/etc/passwd",
        "C:/Windows/system32",
        "src\\legal_ai\\orchestration\\roles.py",
    ):
        with pytest.raises(OrchestrationValidationError):
            assert_write_allowed(configuration, path)


def test_normalisation_is_idempotent_and_strips_noise() -> None:
    assert normalise_repo_path("./src//legal_ai/orchestration/roles.py") == (
        "src/legal_ai/orchestration/roles.py"
    )


@pytest.mark.parametrize(
    "path",
    [
        "src/legal_ai/orchestration/roles.py.",
        "src/legal_ai/orchestration/roles.py ",
        "src/legal_ai/orchestration /roles.py",
        "src/legal_ai/orchestration/roles.py:stream",
        "src/legal_ai/orchestration/CON.py",
        "src/legal_ai/orchestration/nul",
        "src/legal_ai/orchestration/ro\tles.py",
    ],
)
def test_filesystem_aliasing_spellings_are_rejected(path: str) -> None:
    """NTFS strips a trailing dot or space, and reserved names alias devices."""

    with pytest.raises(OrchestrationValidationError):
        normalise_repo_path(path)


def test_non_nfc_unicode_is_rejected_rather_than_normalised() -> None:
    decomposed = "docs/adr/cafe\u0301.md"
    assert unicodedata.normalize("NFC", decomposed) != decomposed
    with pytest.raises(OrchestrationValidationError):
        normalise_repo_path(decomposed)


def test_case_differences_are_not_treated_as_the_same_path() -> None:
    """An exact-match allowlist is case sensitive; the sibling stays refused."""

    configuration = _scoped("src/legal_ai/orchestration/roles.py")
    with pytest.raises(RoleAccessDenied):
        assert_write_allowed(configuration, "src/legal_ai/orchestration/ROLES.py")

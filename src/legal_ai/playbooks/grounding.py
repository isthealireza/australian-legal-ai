"""Fail-closed playbook grounding gates (application boundary only).

Grounding is application-enforced. PostgreSQL enforces lifecycle and payload
immutability but does not validate legal grounding. Privileged direct database
access is outside the application policy boundary.
"""

from __future__ import annotations

from typing import Protocol

from legal_ai.playbooks.errors import GroundingUnavailable, GroundingValidationFailed
from legal_ai.playbooks.types import OperationalClass


class GroundingActivationGate(Protocol):
    """Required gate for every playbook activation path."""

    def assert_may_activate(
        self,
        *,
        playbook_key: str,
        version: int,
        operational_class: OperationalClass,
        content_sha256: str,
    ) -> None:
        """Raise if activation must not proceed."""


class FailClosedGroundingGate:
    """Production Phase 2 gate: all activation attempts fail closed."""

    def assert_may_activate(
        self,
        *,
        playbook_key: str,
        version: int,
        operational_class: OperationalClass,
        content_sha256: str,
    ) -> None:
        del playbook_key, version, operational_class, content_sha256
        raise GroundingUnavailable(
            "Phase 2 has no production grounding validator; activation is refuse-closed"
        )


def require_grounding_gate(gate: GroundingActivationGate | None) -> GroundingActivationGate:
    """Reject missing gates; never default to permit."""

    if gate is None:
        raise GroundingUnavailable("GroundingActivationGate is required; no default permit")
    return gate


# Re-export for typed failure documentation.
__all__ = [
    "FailClosedGroundingGate",
    "GroundingActivationGate",
    "GroundingUnavailable",
    "GroundingValidationFailed",
    "require_grounding_gate",
]

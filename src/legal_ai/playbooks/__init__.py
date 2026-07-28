"""Public Phase 2 playbook package exports.

Grounding is application-enforced. PostgreSQL enforces lifecycle and payload
immutability but does not validate legal grounding.
"""

from legal_ai.playbooks.authority import assert_playbook_action_allowed, effective_ceiling
from legal_ai.playbooks.errors import (
    GroundingUnavailable,
    GroundingValidationFailed,
    PlaybookError,
    PlaybookValidationError,
)
from legal_ai.playbooks.grounding import FailClosedGroundingGate, require_grounding_gate
from legal_ai.playbooks.hashing import canonical_definition_bytes, content_sha256
from legal_ai.playbooks.models import PlaybookDefinitionPayload, validate_definition_payload
from legal_ai.playbooks.rules import evaluate_rule, parse_rule_node
from legal_ai.playbooks.types import (
    OperationalClass,
    PlaybookStatus,
    RuleResult,
)

# Production composition must inject FailClosedGroundingGate only.
PRODUCTION_GROUNDING_GATE = FailClosedGroundingGate()


def production_grounding_gate() -> FailClosedGroundingGate:
    """Return the only production grounding gate (fail-closed)."""

    return PRODUCTION_GROUNDING_GATE


__all__ = [
    "FailClosedGroundingGate",
    "GroundingUnavailable",
    "GroundingValidationFailed",
    "OperationalClass",
    "PlaybookDefinitionPayload",
    "PlaybookError",
    "PlaybookStatus",
    "PlaybookValidationError",
    "RuleResult",
    "assert_playbook_action_allowed",
    "canonical_definition_bytes",
    "content_sha256",
    "effective_ceiling",
    "evaluate_rule",
    "parse_rule_node",
    "production_grounding_gate",
    "require_grounding_gate",
    "validate_definition_payload",
]

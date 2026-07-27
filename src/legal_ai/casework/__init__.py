"""Generic Casework Core (Phase 1)."""

from legal_ai.casework import errors, types
from legal_ai.casework.authority import assert_action_allowed
from legal_ai.casework.state_machine import allowed_targets, assert_transition_allowed

__all__ = [
    "assert_action_allowed",
    "assert_transition_allowed",
    "allowed_targets",
    "errors",
    "types",
]

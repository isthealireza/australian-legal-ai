"""Phase 1 action-authority policy (L0–L2 only)."""

from __future__ import annotations

from legal_ai.casework.errors import ActionAuthorityDenied
from legal_ai.casework.types import (
    PHASE1_AUTHORITY_CEILINGS,
    ActionAuthorityLevel,
    authority_rank,
)


def assert_action_allowed(
    *,
    required: ActionAuthorityLevel,
    ceiling: ActionAuthorityLevel,
    command_type: str,
) -> None:
    """Deny L3+ and any required level above the matter ceiling."""

    if required not in PHASE1_AUTHORITY_CEILINGS:
        raise ActionAuthorityDenied(
            required=required,
            ceiling=ceiling,
            command_type=command_type,
        )
    if ceiling not in PHASE1_AUTHORITY_CEILINGS:
        raise ActionAuthorityDenied(
            required=required,
            ceiling=ceiling,
            command_type=command_type,
        )
    if authority_rank(required) > authority_rank(ceiling):
        raise ActionAuthorityDenied(
            required=required,
            ceiling=ceiling,
            command_type=command_type,
        )

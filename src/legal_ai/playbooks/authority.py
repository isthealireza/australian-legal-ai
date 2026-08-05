"""Effective authority ceiling for playbook-scoped operations."""

from __future__ import annotations

from legal_ai.casework.types import ActionAuthorityLevel, authority_rank
from legal_ai.playbooks.errors import PlaybookAuthorityDenied
from legal_ai.playbooks.types import PHASE2_AUTHORITY_CEILINGS, PlaybookStatus


def effective_ceiling(
    *,
    matter_ceiling: ActionAuthorityLevel,
    playbook_max_authority: ActionAuthorityLevel,
) -> ActionAuthorityLevel:
    """Return min(matter ceiling, playbook max) under L0–L2 only."""

    if matter_ceiling not in PHASE2_AUTHORITY_CEILINGS:
        raise PlaybookAuthorityDenied(
            required=matter_ceiling,
            effective_ceiling=ActionAuthorityLevel.L0,
            command_type="effective_ceiling",
        )
    if playbook_max_authority not in PHASE2_AUTHORITY_CEILINGS:
        raise PlaybookAuthorityDenied(
            required=playbook_max_authority,
            effective_ceiling=ActionAuthorityLevel.L0,
            command_type="effective_ceiling",
        )
    if authority_rank(matter_ceiling) <= authority_rank(playbook_max_authority):
        return matter_ceiling
    return playbook_max_authority


def assert_playbook_action_allowed(
    *,
    required: ActionAuthorityLevel,
    matter_ceiling: ActionAuthorityLevel,
    playbook_max_authority: ActionAuthorityLevel,
    playbook_status: PlaybookStatus,
    command_type: str,
) -> ActionAuthorityLevel:
    """Central policy boundary for every playbook operation."""

    if playbook_status is not PlaybookStatus.ACTIVE:
        raise PlaybookAuthorityDenied(
            required=required,
            effective_ceiling=ActionAuthorityLevel.L0,
            command_type=command_type,
        )
    ceiling = effective_ceiling(
        matter_ceiling=matter_ceiling,
        playbook_max_authority=playbook_max_authority,
    )
    if required not in PHASE2_AUTHORITY_CEILINGS:
        raise PlaybookAuthorityDenied(
            required=required,
            effective_ceiling=ceiling,
            command_type=command_type,
        )
    if authority_rank(required) > authority_rank(ceiling):
        raise PlaybookAuthorityDenied(
            required=required,
            effective_ceiling=ceiling,
            command_type=command_type,
        )
    return ceiling

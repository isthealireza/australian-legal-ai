"""Unit tests for Phase 1 action-authority policy."""

import pytest

from legal_ai.casework.authority import assert_action_allowed
from legal_ai.casework.errors import ActionAuthorityDenied
from legal_ai.casework.types import ActionAuthorityLevel


def test_l0_read_allowed_under_l0_ceiling() -> None:
    assert_action_allowed(
        required=ActionAuthorityLevel.L0,
        ceiling=ActionAuthorityLevel.L0,
        command_type="GetMatter",
    )


def test_l1_write_blocked_by_l0_ceiling() -> None:
    with pytest.raises(ActionAuthorityDenied) as exc_info:
        assert_action_allowed(
            required=ActionAuthorityLevel.L1,
            ceiling=ActionAuthorityLevel.L0,
            command_type="AddFact",
        )
    assert exc_info.value.required is ActionAuthorityLevel.L1


def test_l3_rejected_even_with_high_ceiling_value() -> None:
    with pytest.raises(ActionAuthorityDenied) as exc_info:
        assert_action_allowed(
            required=ActionAuthorityLevel.L3,
            ceiling=ActionAuthorityLevel.L2,
            command_type="SendEmail",
        )
    assert exc_info.value.command_type == "SendEmail"


def test_l2_allowed_when_ceiling_l2() -> None:
    assert_action_allowed(
        required=ActionAuthorityLevel.L2,
        ceiling=ActionAuthorityLevel.L2,
        command_type="FutureDraft",
    )

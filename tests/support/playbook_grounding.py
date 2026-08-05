"""Test-only synthetic grounding gate. Never import from production wiring."""

from __future__ import annotations

from legal_ai.playbooks.errors import GroundingUnavailable
from legal_ai.playbooks.types import OperationalClass

_SYNTHETIC_KEY_PREFIX = "synthetic_"
_FORBIDDEN_PRODUCT_KEYS = frozenset({"wa_motor_property_damage"})


class PermitSyntheticGroundingGate:
    """Permits activation only for synthetic fixture playbooks in tests."""

    def assert_may_activate(
        self,
        *,
        playbook_key: str,
        version: int,
        operational_class: OperationalClass,
        content_sha256: str,
    ) -> None:
        del version, content_sha256
        if playbook_key in _FORBIDDEN_PRODUCT_KEYS:
            raise GroundingUnavailable(f"synthetic gate never permits product key {playbook_key}")
        if operational_class is OperationalClass.SYNTHETIC_FIXTURE:
            return
        if playbook_key.startswith(_SYNTHETIC_KEY_PREFIX):
            return
        raise GroundingUnavailable(
            "PermitSyntheticGroundingGate only allows synthetic_* keys or SYNTHETIC_FIXTURE"
        )

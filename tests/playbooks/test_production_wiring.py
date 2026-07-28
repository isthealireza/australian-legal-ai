"""Production grounding wiring must stay fail-closed."""

from __future__ import annotations

import importlib
import inspect

from legal_ai.playbooks import production_grounding_gate
from legal_ai.playbooks.grounding import FailClosedGroundingGate


def test_production_grounding_gate_is_fail_closed() -> None:
    gate = production_grounding_gate()
    assert isinstance(gate, FailClosedGroundingGate)
    assert type(gate) is FailClosedGroundingGate


def test_permit_synthetic_gate_not_imported_from_playbooks_package() -> None:
    module = importlib.import_module("legal_ai.playbooks")
    source = inspect.getsource(module)
    assert "PermitSyntheticGroundingGate" not in source
    assert "tests.support" not in source
    assert not hasattr(module, "PermitSyntheticGroundingGate")


def test_cli_uses_fail_closed_gate() -> None:
    cli = importlib.import_module("legal_ai.playbooks.cli")
    source = inspect.getsource(cli)
    assert "FailClosedGroundingGate" in source
    assert "PermitSyntheticGroundingGate" not in source

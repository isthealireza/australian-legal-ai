"""FAMILY 1 — GROUNDED.

The corpus holds the provision. Expected outcome: a validated evidence packet
with the right pinpoint, whose citation resolves to a recorded digest.

Every asserted value below is copied verbatim from
``tests/fixtures/wa_legislation/*/*.manifest.json`` and the derived
``provisions/*.provision.json`` files. Nothing here is written from legal
knowledge.
"""

from __future__ import annotations

import hashlib

import pytest

from legal_ai.research.service import ResearchValidated
from legal_ai.research.types import LegalStatus, ResearchAuditResult
from tests.scenarios.conftest import (
    FIXTURE_ROOT,
    MANIFEST_BY_TITLE,
    new_service,
    wa_query,
)

# (act_title, provision_identifier, pinpoint, provision_heading)
_SCENARIOS = (
    (
        "Road Traffic Act 1974",
        "s 55",
        "section 55",
        "Driver in incident occasioning property damage to stop and give information",
    ),
    (
        "Road Traffic Act 1974",
        "s 56",
        "section 56",
        "Driver in incident occasioning bodily harm or property damage to report incident to "
        "police",
    ),
    ("Sale of Goods Act 1895", "s 13", "section 13", "Sale by description"),
    (
        "Sale of Goods Act 1895",
        "s 14",
        "section 14",
        "Implied conditions as to quality or fitness",
    ),
    ("Sale of Goods Act 1895", "s 15", "section 15", "Sale by sample"),
    ("Sale of Goods Act 1895", "s 16", "section 16", "Goods must be ascertained"),
    ("Fair Trading Act 2010", "s 18", "section 18", "Australian Consumer Law text"),
    (
        "Fair Trading Act 2010",
        "s 19",
        "section 19",
        "Application of Australian Consumer Law text",
    ),
    (
        "Building and Construction Industry (Security of Payment) Act 2021",
        "s 17",
        "section 17",
        "Right to progress payments",
    ),
    (
        "Building and Construction Industry (Security of Payment) Act 2021",
        "s 25",
        "section 25",
        "Response to payment claim: payment schedule",
    ),
    ("Motor Vehicle Dealers Act 1973", "s 5", "section 5", "Terms used"),
    (
        "Motor Vehicle Dealers Act 1973",
        "s 30",
        "section 30",
        "Unlicensed dealing etc., offences as to",
    ),
    (
        "Owner-Drivers (Contracts and Disputes) Act 2007",
        "s 4",
        "section 4",
        "Term used: owner-driver",
    ),
    (
        "Owner-Drivers (Contracts and Disputes) Act 2007",
        "s 7",
        "section 7",
        "Act prevails over owner-driver contracts",
    ),
)


@pytest.mark.parametrize(
    ("act_title", "identifier", "pinpoint", "heading"),
    _SCENARIOS,
    ids=[f"{title}-{identifier}".replace(" ", "-") for title, identifier, _, _ in _SCENARIOS],
)
def test_grounded_scenario_yields_a_complete_validated_packet(
    act_title: str, identifier: str, pinpoint: str, heading: str
) -> None:
    scenario = wa_query(
        act_title=act_title,
        provision_identifier=identifier,
        pinpoint=pinpoint,
    )
    manifest = MANIFEST_BY_TITLE[act_title]

    result = new_service().research(scenario)

    assert isinstance(result, ResearchValidated)
    packet = result.packet
    # Fixture identity, verbatim from the manifest.
    assert packet.source_id == f"wa_legislation:{manifest[0]}:consolidated:{manifest[3]}"
    assert packet.source_system == "wa_legislation"
    assert packet.jurisdiction == "WA"
    assert packet.act.title == act_title
    assert packet.act.jurisdiction == "WA"
    assert packet.act.act_number == manifest[2]
    assert packet.official_source_url == manifest[8]
    # The requested pinpoint resolves to the recorded provision, verbatim.
    assert packet.provision_identifier == identifier
    assert packet.pinpoint == pinpoint
    assert packet.provision_heading == heading
    # Provenance, verbatim from the manifest.
    assert packet.source_version == manifest[3]
    assert packet.compilation_date == manifest[4]
    assert packet.legal_status is LegalStatus.IN_FORCE
    assert packet.status_date == manifest[5]
    assert packet.retrieved_at == manifest[6]
    assert packet.audit_result is ResearchAuditResult.RECORDED
    # The citation resolves to a recorded digest: the packet digest equals the
    # manifest digest over the exact recorded bytes on disk.
    on_disk = (FIXTURE_ROOT / manifest[0] / manifest[9]).read_bytes()
    assert packet.source_content == on_disk
    assert packet.sha256 == manifest[7]
    assert hashlib.sha256(on_disk).hexdigest() == manifest[7]
    assert hashlib.sha256(packet.source_content).hexdigest() == packet.sha256


def test_every_recorded_act_is_reachable_by_exact_title() -> None:
    # One grounded query per recorded Act proves each of the six manifests
    # selects exactly once and validates (no AmbiguousSelection, no refusal).
    reachable = (
        ("Road Traffic Act 1974", "s 55", "section 55"),
        ("Sale of Goods Act 1895", "s 13", "section 13"),
        ("Fair Trading Act 2010", "s 18", "section 18"),
        ("Building and Construction Industry (Security of Payment) Act 2021", "s 17", "section 17"),
        ("Motor Vehicle Dealers Act 1973", "s 5", "section 5"),
        ("Owner-Drivers (Contracts and Disputes) Act 2007", "s 4", "section 4"),
    )
    service = new_service()

    for act_title, identifier, pinpoint in reachable:
        result = service.research(
            wa_query(act_title=act_title, provision_identifier=identifier, pinpoint=pinpoint)
        )
        assert isinstance(result, ResearchValidated), (act_title, result)
        assert result.packet.sha256 == MANIFEST_BY_TITLE[act_title][7]

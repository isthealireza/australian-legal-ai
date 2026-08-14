"""Unit tests for the WA evidence-packet contract itself."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from legal_ai.research.models import ActIdentity, PacketDraft, WaEvidencePacket
from legal_ai.research.types import LegalStatus, ResearchAuditResult
from legal_ai.research.validation import validate_recorded_source
from tests.research.conftest import query, recorded_source


def _draft() -> PacketDraft:
    draft = validate_recorded_source(query(), recorded_source())
    assert isinstance(draft, PacketDraft)
    return draft


def _packet_fields(packet: WaEvidencePacket, **overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "source_id": packet.source_id,
        "source_system": packet.source_system,
        "jurisdiction": packet.jurisdiction,
        "official_source_url": packet.official_source_url,
        "act": packet.act,
        "provision_identifier": packet.provision_identifier,
        "pinpoint": packet.pinpoint,
        "provision_heading": packet.provision_heading,
        "source_version": packet.source_version,
        "compilation_date": packet.compilation_date,
        "legal_status": packet.legal_status,
        "status_date": packet.status_date,
        "source_content": packet.source_content,
        "retrieved_at": packet.retrieved_at,
        "sha256": packet.sha256,
        "audit_result": packet.audit_result,
    }
    fields.update(overrides)
    return fields


def test_packet_carries_every_required_field() -> None:
    packet = _draft().to_packet()

    assert packet.source_system == "wa_legislation"
    assert packet.jurisdiction == "WA"
    assert packet.act.jurisdiction == "WA"
    assert packet.act.title == "Synthetic Act 1974"
    assert packet.official_source_url.startswith("https://www.legislation.wa.gov.au/")
    assert packet.provision_identifier == "s 55"
    assert packet.pinpoint == "section 55"
    assert packet.source_version == "1-a0-00"
    assert packet.compilation_date == date(2025, 1, 10)
    assert packet.legal_status is LegalStatus.IN_FORCE
    assert packet.status_date == date(2025, 1, 10)
    assert packet.retrieved_at == datetime(2026, 8, 11, 10, 27, 3, tzinfo=UTC)
    assert packet.sha256 == hashlib.sha256(packet.source_content).hexdigest()
    assert packet.audit_result is ResearchAuditResult.RECORDED


def test_packet_is_frozen() -> None:
    packet = _draft().to_packet()

    with pytest.raises(ValidationError):
        packet.sha256 = "0" * 64


def test_packet_forbids_extra_fields() -> None:
    packet = _draft().to_packet()

    with pytest.raises(ValidationError):
        WaEvidencePacket(**_packet_fields(packet, legal_proposition="a driver must stop"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"sha256": hashlib.sha256(b"different bytes").hexdigest()},
        {"source_content": b"different bytes"},
        {"legal_status": LegalStatus.UNKNOWN},
        {"source_content": b""},
        {"retrieved_at": datetime(2026, 8, 11, 10, 27, 3)},
        {"source_version": None, "compilation_date": None},
        {"official_source_url": "https://legislation.nsw.gov.au/law.html"},
        {"official_source_url": "http://www.legislation.wa.gov.au/law.html"},
        {"status_date": date(2026, 8, 12)},
        {"sha256": "not-a-digest"},
        {"source_id": "  "},
    ],
)
def test_packet_contract_rejects_inconsistent_or_invalid_fields(
    overrides: dict[str, Any],
) -> None:
    draft = replace(_draft(), **overrides)

    with pytest.raises(ValidationError):
        draft.to_packet()


def test_packet_cannot_be_constructed_without_a_recorded_audit_result() -> None:
    packet = _draft().to_packet()

    with pytest.raises(ValidationError):
        WaEvidencePacket(**_packet_fields(packet, audit_result="PENDING"))


def test_packet_cannot_carry_a_non_wa_act_identity() -> None:
    packet = _draft().to_packet()
    non_wa_act: dict[str, Any] = {"title": "Road Transport Act 2013", "jurisdiction": "NSW"}

    with pytest.raises(ValidationError):
        ActIdentity(**non_wa_act)
    with pytest.raises(ValidationError):
        WaEvidencePacket(**_packet_fields(packet, act=non_wa_act))


def test_packet_cannot_declare_a_non_wa_source_system_or_jurisdiction() -> None:
    packet = _draft().to_packet()

    with pytest.raises(ValidationError):
        WaEvidencePacket(**_packet_fields(packet, source_system="federal_register"))
    with pytest.raises(ValidationError):
        WaEvidencePacket(**_packet_fields(packet, jurisdiction="NSW"))

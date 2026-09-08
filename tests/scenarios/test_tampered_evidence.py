"""FAMILY 6 — TAMPERED EVIDENCE.

A mutated digest, a foreign host, or a stale/untrustworthy version must fail
closed with the correct typed refusal code. The tamper base is the committed
Road Traffic Act 1974 fixture (``road_traffic_act_1974/``); every mutation is
applied to an in-memory copy so the recorded bytes on disk are never touched.
A refused run must never expose a packet, a citation, or a digest — not even
inside the audit event (PROJECT_GOVERNANCE.md section 2.4 and 8).
"""

from __future__ import annotations

import pytest

from legal_ai.research.service import ResearchRefused
from legal_ai.research.types import ResearchOutcome, ResearchRefusalCode
from tests.scenarios.conftest import service_over, tampered_source, wa_query

# (mutation, expected_refusal_code, why)
_TAMPERS = (
    (
        {"source_content": b"tampered official text"},
        ResearchRefusalCode.HASH_MISMATCH,
        "content mutated while the recorded digest is kept: the recomputed digest no longer "
        "matches, so the evidence fails integrity (validation step 3)",
    ),
    (
        {"sha256": "not-a-digest"},
        ResearchRefusalCode.FIELD_INVALID,
        "the recorded digest is structurally invalid, so it cannot vouch for the content",
    ),
    (
        {"official_source_url": "https://legislation.nsw.gov.au/view/act-1974-059.html"},
        ResearchRefusalCode.SOURCE_NOT_ALLOWLISTED,
        "the official-source URL host is outside the closed WA host allowlist",
    ),
    (
        {"official_source_url": "https://attacker.example/#www.legislation.wa.gov.au"},
        ResearchRefusalCode.SOURCE_NOT_ALLOWLISTED,
        "an allowlisted substring in a fragment cannot launder a foreign host",
    ),
    (
        {"status_date": "2030-01-01"},
        ResearchRefusalCode.STATUS_DATE_INVALID,
        "a status date that postdates the retrieval timestamp claims a currency that cannot "
        "be proven; the stale/future version is not trusted",
    ),
    (
        {"source_system": "wa_legislation_prod"},
        ResearchRefusalCode.SOURCE_SYSTEM_MISMATCH,
        "the provenance system identifier is not the recorded 'wa_legislation'",
    ),
)


@pytest.mark.parametrize(
    ("overrides", "expected", "why"),
    _TAMPERS,
    ids=[code.value for _, code, _ in _TAMPERS],
)
def test_tampered_evidence_fails_closed(
    overrides: dict[str, object], expected: ResearchRefusalCode, why: str
) -> None:
    service, sink = service_over(tampered_source(**overrides))

    result = service.research(
        wa_query(
            act_title="Road Traffic Act 1974",
            provision_identifier="s 55",
            pinpoint="section 55",
        )
    )

    # Tamper: {why}
    assert isinstance(result, ResearchRefused)
    assert result.code is expected
    assert not hasattr(result, "packet")
    event = sink.events[-1]
    assert event.outcome is ResearchOutcome.REFUSED
    assert event.refusal_code is expected
    # A refused outcome must not carry a citation or a digest, even in audit.
    assert event.source_id is None
    assert event.sha256 is None

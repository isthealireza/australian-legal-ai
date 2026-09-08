"""FAMILY 3 — WRONG JURISDICTION.

A New South Wales or Victorian problem against a WA corpus must be refused
with ``JURISDICTION_MISMATCH`` before any retrieval. Cross-jurisdiction
contamination is a release-blocking defect (PROJECT_GOVERNANCE.md section 4).

Grounding: the check is jurisdictional and runs before corpus selection, so
these scenarios refuse even when the Act title is a recorded WA manifest
(e.g. ``Road Traffic Act 1974``). No WA evidence packet may leave the boundary
for a non-WA request.
"""

from __future__ import annotations

import pytest

from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.service import ResearchRefused, WaResearchService
from legal_ai.research.types import ResearchOutcome, ResearchRefusalCode
from tests.scenarios.conftest import FIXTURE_ROOT, new_service, wa_query
from tests.support.research_audit import InMemoryResearchAuditSink

# (jurisdiction, act_title, provision_identifier, pinpoint)
_SCENARIOS = (
    # A real NSW Act, same section number that is recorded for the WA SoG 1895:
    # s 13 must never be answered from the WA Sale of Goods Act.
    ("NSW", "Goods Act 1958", "s 13", "section 13"),
    # A real NSW Act with no WA counterpart in the corpus.
    ("NSW", "Motor Accident Injuries Act 2017", "s 4", "section 4"),
    # A Victoria problem against a recorded WA title: the recorded corpus still
    # cannot be used, because the request is not WA.
    ("VIC", "Road Traffic Act 1974", "s 55", "section 55"),
    # A spelled-out jurisdiction value.
    ("New South Wales", "Limitation Act 1969", "s 14", "section 14"),
)


@pytest.mark.parametrize(
    ("jurisdiction", "act_title", "identifier", "pinpoint"),
    _SCENARIOS,
    ids=[
        f"{jurisdiction}-{act_title}".replace(" ", "-")
        for jurisdiction, act_title, _, _ in _SCENARIOS
    ],
)
def test_wrong_jurisdiction_scenario_refuses_before_retrieval(
    jurisdiction: str, act_title: str, identifier: str, pinpoint: str
) -> None:
    service = new_service()

    result = service.research(
        wa_query(
            jurisdiction=jurisdiction,
            act_title=act_title,
            provision_identifier=identifier,
            pinpoint=pinpoint,
        )
    )

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.JURISDICTION_MISMATCH
    # A refusal never exposes a packet, a citation, or a digest.
    assert not hasattr(result, "packet")


def test_wrong_jurisdiction_refusal_is_audited_without_a_citation() -> None:
    sink = InMemoryResearchAuditSink()
    service = WaResearchService(
        corpus=RecordedWaCorpus(FIXTURE_ROOT),
        audit_sink=sink,
    )
    result = service.research(wa_query(jurisdiction="NSW"))
    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.JURISDICTION_MISMATCH
    event = sink.events[-1]
    assert event.outcome is ResearchOutcome.REFUSED
    assert event.refusal_code is ResearchRefusalCode.JURISDICTION_MISMATCH
    assert event.source_id is None
    assert event.sha256 is None

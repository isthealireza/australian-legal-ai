"""Positive end-to-end tests over the two extra recorded WA fixtures.

These tests read the committed Sale of Goods Act 1895 (WA) and Fair Trading
Act 2010 (WA) fixtures only. They never modify them, never retrieve a new
copy, and never touch the network.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pytest

from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.service import ResearchValidated, WaResearchService
from legal_ai.research.types import LegalStatus, ResearchAuditResult
from tests.research.conftest import RECORDED_FIXTURE_ROOT, recorded_query
from tests.support.research_audit import InMemoryResearchAuditSink

# (act_dir, act_title, source_version, act_number, compilation_date,
#  status_date, retrieved_at, sha256, official_source_url, pdf file)
_SOG = (
    "sale_of_goods_act_1895",
    "Sale of Goods Act 1895",
    "05-d0-06",
    "041 of 1895 (59Vict No 41)",
    date(2010, 9, 11),
    date(2010, 9, 11),
    datetime(2026, 9, 8, 2, 16, 40, tzinfo=UTC),
    "5e3a298c37d2d32aaad9a2eaaa61c44164b9144875316bf080b649a1b50081e1",
    "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a726.html&view=consolidated",
    "sale_of_goods_act_1895_consolidated_05-d0-06.pdf",
)
_FTA = (
    "fair_trading_act_2010",
    "Fair Trading Act 2010",
    "02-m0-00",
    "057 of 2010",
    date(2025, 9, 25),
    date(2025, 9, 25),
    datetime(2026, 9, 8, 2, 16, 40, tzinfo=UTC),
    "8f4760052a16f26218e506e9c78bbd15bcbf512dbc17d37e4e9bd8e148c1e8eb",
    "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a146804.html&view=consolidated",
    "fair_trading_act_2010_consolidated_02-m0-00.pdf",
)

# (act_dir, act_title, identifier, pinpoint, heading)
_NEW_PROVISIONS = [
    (
        "sale_of_goods_act_1895",
        "Sale of Goods Act 1895",
        "s 13",
        "section 13",
        "Sale by description",
    ),
    (
        "sale_of_goods_act_1895",
        "Sale of Goods Act 1895",
        "s 14",
        "section 14",
        "Implied conditions as to quality or fitness",
    ),
    (
        "sale_of_goods_act_1895",
        "Sale of Goods Act 1895",
        "s 15",
        "section 15",
        "Sale by sample",
    ),
    (
        "sale_of_goods_act_1895",
        "Sale of Goods Act 1895",
        "s 16",
        "section 16",
        "Goods must be ascertained",
    ),
    (
        "fair_trading_act_2010",
        "Fair Trading Act 2010",
        "s 18",
        "section 18",
        "Australian Consumer Law text",
    ),
    (
        "fair_trading_act_2010",
        "Fair Trading Act 2010",
        "s 19",
        "section 19",
        "Application of Australian Consumer Law text",
    ),
]

_RECORDS = {record[0]: record for record in (_SOG, _FTA)}


def _service() -> WaResearchService:
    return WaResearchService(
        corpus=RecordedWaCorpus(RECORDED_FIXTURE_ROOT),
        audit_sink=InMemoryResearchAuditSink(),
    )


@pytest.mark.parametrize(
    ("act_dir", "act_title", "identifier", "pinpoint", "heading"),
    [(row[0], row[1], row[2], row[3], row[4]) for row in _NEW_PROVISIONS],
    ids=[f"{row[0]}-{row[2]}".replace(" ", "-") for row in _NEW_PROVISIONS],
)
def test_each_new_pinned_provision_yields_a_complete_validated_packet(
    act_dir: str, act_title: str, identifier: str, pinpoint: str, heading: str
) -> None:
    (
        _,
        _title,
        source_version,
        act_number,
        compilation_date,
        status_date,
        retrieved_at,
        sha256,
        official_source_url,
        pdf_file,
    ) = _RECORDS[act_dir]

    result = _service().research(
        recorded_query(act_title=act_title, provision_identifier=identifier, pinpoint=pinpoint)
    )

    assert isinstance(result, ResearchValidated)
    packet = result.packet
    assert packet.source_system == "wa_legislation"
    assert packet.jurisdiction == "WA"
    assert packet.act.title == act_title
    assert packet.act.jurisdiction == "WA"
    assert packet.act.act_number == act_number
    assert packet.official_source_url == official_source_url
    assert packet.provision_identifier == identifier
    assert packet.pinpoint == pinpoint
    assert packet.provision_heading == heading
    assert packet.source_version == source_version
    assert packet.compilation_date == compilation_date
    assert packet.legal_status is LegalStatus.IN_FORCE
    assert packet.status_date == status_date
    assert packet.retrieved_at == retrieved_at
    assert packet.sha256 == sha256
    assert len(packet.sha256) == 64
    assert all(character in "0123456789abcdef" for character in packet.sha256)
    on_disk = (RECORDED_FIXTURE_ROOT / act_dir / pdf_file).read_bytes()
    assert packet.source_content == on_disk
    assert packet.source_content
    assert packet.audit_result is ResearchAuditResult.RECORDED


@pytest.mark.parametrize(
    "act_dir",
    ["sale_of_goods_act_1895", "fair_trading_act_2010"],
    ids=["sog", "fta"],
)
def test_new_fixtures_have_unmodified_recorded_bytes(act_dir: str) -> None:
    record = _RECORDS[act_dir]

    on_disk = (RECORDED_FIXTURE_ROOT / act_dir / record[9]).read_bytes()

    assert hashlib.sha256(on_disk).hexdigest() == record[7]


@pytest.mark.parametrize(
    "act_title",
    ["Sale of Goods Act 1895", "Fair Trading Act 2010"],
    ids=["sog", "fta"],
)
def test_new_fixtures_are_selected_by_title_and_match_exactly_once(act_title: str) -> None:
    corpus = RecordedWaCorpus(RECORDED_FIXTURE_ROOT)

    source = corpus.select(recorded_query(act_title=act_title))

    # A second recorded source with the same title would make this raise
    # AmbiguousSelection rather than guess, so a single non-None result
    # proves the title matches exactly once.
    assert source is not None
    assert source.act_title == act_title
    assert source.source_system == "wa_legislation"
    assert source.jurisdiction == "WA"

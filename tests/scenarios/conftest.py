"""Shared grounding constants and builders for the scenario test suite.

THE GROUNDING HARD RULE: every expected Act title, section number, provision
heading, version, date, URL, digest and legal status asserted in this suite is
copied verbatim from a manifest under ``tests/fixtures/wa_legislation/`` or
from the provision metadata derived from those manifests. No expected value is
produced from model knowledge. Where a scenario cannot be grounded, the
expected outcome is a typed refusal and the reason is written in the scenario.

These are tests only. Nothing here imports or modifies production wiring.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.models import RecordedWaSource, ResearchQuery
from legal_ai.research.service import WaResearchService
from tests.support.research_audit import InMemoryResearchAuditSink

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "wa_legislation"

ACT_TITLES = (
    "Road Traffic Act 1974",
    "Sale of Goods Act 1895",
    "Fair Trading Act 2010",
    "Building and Construction Industry (Security of Payment) Act 2021",
    "Motor Vehicle Dealers Act 1973",
    "Owner-Drivers (Contracts and Disputes) Act 2007",
)


def wa_query(
    *,
    jurisdiction: str = "WA",
    act_title: str = "Road Traffic Act 1974",
    provision_identifier: str = "s 55",
    pinpoint: str = "section 55",
) -> ResearchQuery:
    """Build one research query (default: the recorded RTA s 55 pinpoint)."""

    return ResearchQuery(
        jurisdiction=jurisdiction,
        act_title=act_title,
        provision_identifier=provision_identifier,
        pinpoint=pinpoint,
    )


def new_service() -> WaResearchService:
    """A service over the committed recorded WA corpus plus an in-memory sink."""

    return WaResearchService(
        corpus=RecordedWaCorpus(FIXTURE_ROOT),
        audit_sink=InMemoryResearchAuditSink(),
    )


def service_over(source: RecordedWaSource) -> tuple[WaResearchService, InMemoryResearchAuditSink]:
    """A service over one in-memory recorded source (on-disk bytes untouched)."""

    sink = InMemoryResearchAuditSink()
    return (
        WaResearchService(
            corpus=_SingleSourceCorpus(source),
            audit_sink=sink,
        ),
        sink,
    )


class _SingleSourceCorpus:
    """Serves exactly one in-memory source, selected by recorded Act title."""

    def __init__(self, source: RecordedWaSource) -> None:
        self._source = source

    def select(self, query: ResearchQuery) -> RecordedWaSource | None:
        from legal_ai.research.corpus import normalize_for_match

        recorded_title = normalize_for_match(self._source.act_title or "")
        if recorded_title == normalize_for_match(query.act_title):
            return self._source
        return None


def load_recorded_source(*, act_title: str) -> RecordedWaSource:
    """Load the committed recorded source for one Act, read-only."""

    source = RecordedWaCorpus(FIXTURE_ROOT).select(wa_query(act_title=act_title))
    if source is None:
        raise AssertionError(f"recorded WA source not found beneath {FIXTURE_ROOT}")
    return source


def without_packet(result: object) -> bool:
    """True when a result exposes no ``packet`` attribute at all."""

    return not hasattr(result, "packet")


# --- Verbatim manifest values (grounding source of truth) -------------------
# (act_dir, act_title, act_number, source_version, compilation_date,
#  status_date, retrieved_at, sha256, official_source_url, pdf_basename)

MANIFESTS: tuple[tuple[str, str, str, str, date, date, datetime, str, str, str], ...] = (
    (
        "road_traffic_act_1974",
        "Road Traffic Act 1974",
        "059 of 1974",
        "14-t0-00",
        date(2025, 1, 10),
        date(2025, 1, 10),
        datetime(2026, 8, 11, 10, 27, 3, tzinfo=UTC),
        "61dbca2d8eddc33a3ebc759b8759886192efaa8b09440089541efd35ed19c525",
        "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a703.html&view=consolidated",
        "road_traffic_act_1974_consolidated_14-t0-00.pdf",
    ),
    (
        "sale_of_goods_act_1895",
        "Sale of Goods Act 1895",
        "041 of 1895 (59Vict No 41)",
        "05-d0-06",
        date(2010, 9, 11),
        date(2010, 9, 11),
        datetime(2026, 9, 8, 2, 16, 40, tzinfo=UTC),
        "5e3a298c37d2d32aaad9a2eaaa61c44164b9144875316bf080b649a1b50081e1",
        "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a726.html&view=consolidated",
        "sale_of_goods_act_1895_consolidated_05-d0-06.pdf",
    ),
    (
        "fair_trading_act_2010",
        "Fair Trading Act 2010",
        "057 of 2010",
        "02-m0-00",
        date(2025, 9, 25),
        date(2025, 9, 25),
        datetime(2026, 9, 8, 2, 16, 40, tzinfo=UTC),
        "8f4760052a16f26218e506e9c78bbd15bcbf512dbc17d37e4e9bd8e148c1e8eb",
        "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a146804.html&view=consolidated",
        "fair_trading_act_2010_consolidated_02-m0-00.pdf",
    ),
    (
        "building_and_construction_industry_security_of_payment_act_2021",
        "Building and Construction Industry (Security of Payment) Act 2021",
        "004 of 2021",
        "00-e0-00",
        date(2024, 2, 1),
        date(2024, 2, 1),
        datetime(2026, 9, 8, 4, 18, 9, tzinfo=UTC),
        "9d78bc1fc594d61af5ec095c03d18b7c266aeb8fe52fd776611dee57574edd5b",
        "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a147300.html",
        "building_and_construction_industry_security_of_payment_act_2021_consolidated_00-e0-00.pdf",
    ),
    (
        "motor_vehicle_dealers_act_1973",
        "Motor Vehicle Dealers Act 1973",
        "101 of 1973",
        "06-k0-01",
        date(2022, 7, 1),
        date(2022, 7, 1),
        datetime(2026, 9, 8, 4, 18, 48, tzinfo=UTC),
        "d91d26a14da9be42c0c477c4ae15a8e9171d11ae68ea5fc77889042a2a1e9990",
        "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a525.html",
        "motor_vehicle_dealers_act_1973_consolidated_06-k0-01.pdf",
    ),
    (
        "owner_drivers_contracts_and_disputes_act_2007",
        "Owner-Drivers (Contracts and Disputes) Act 2007",
        "007 of 2007",
        "01-g0-00",
        date(2025, 1, 31),
        date(2025, 1, 31),
        datetime(2026, 9, 8, 4, 19, 20, tzinfo=UTC),
        "03071c9fe15dfdc3a8c26ebfd9027f5ff6044f91c83e0455ace5b5ac40b43bad",
        "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a146614.html",
        "owner_drivers_contracts_and_disputes_act_2007_consolidated_01-g0-00.pdf",
    ),
)

MANIFEST_BY_TITLE: dict[str, tuple[str, str, str, str, date, date, datetime, str, str, str]] = {
    record[1]: record for record in MANIFESTS
}


def tampered_source(**overrides: Any) -> RecordedWaSource:
    """The recorded RTA source with fields replaced in memory only."""

    return replace(load_recorded_source(act_title="Road Traffic Act 1974"), **overrides)

"""Positive integration tests for the three recorded WA corpus-slice fixtures.

These tests read the committed Owner-Drivers (Contracts and Disputes) Act 2007,
Motor Vehicle Dealers Act 1973 and Building and Construction Industry (Security
of Payment) Act 2021 (WA) fixtures only. They never modify them, never retrieve
a new copy, and never touch the network.

Packet validation, byte integrity and derivation-digest checks mirror
``test_recorded_fixture_sog_rta.py`` and ``test_recorded_provision_digests.py``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from scripts.derive_wa_provisions import NEWLINE, _document_lines

from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.service import ResearchValidated, WaResearchService
from legal_ai.research.types import LegalStatus, ResearchAuditResult
from tests.research.conftest import RECORDED_FIXTURE_ROOT, recorded_query
from tests.support.research_audit import InMemoryResearchAuditSink

# (act_dir, act_title, source_version, act_number, compilation_date,
#  status_date, retrieved_at, sha256, official_source_url, pdf file)
_RECORDS = {
    "building_and_construction_industry_security_of_payment_act_2021": (
        "building_and_construction_industry_security_of_payment_act_2021",
        "Building and Construction Industry (Security of Payment) Act 2021",
        "00-e0-00",
        "004 of 2021",
        date(2024, 2, 1),
        date(2024, 2, 1),
        datetime(2026, 9, 8, 4, 18, 9, tzinfo=UTC),
        "9d78bc1fc594d61af5ec095c03d18b7c266aeb8fe52fd776611dee57574edd5b",
        "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a147300.html",
        "building_and_construction_industry_security_of_payment_act_2021_consolidated_00-e0-00.pdf",
    ),
    "motor_vehicle_dealers_act_1973": (
        "motor_vehicle_dealers_act_1973",
        "Motor Vehicle Dealers Act 1973",
        "06-k0-01",
        "101 of 1973",
        date(2022, 7, 1),
        date(2022, 7, 1),
        datetime(2026, 9, 8, 4, 18, 48, tzinfo=UTC),
        "d91d26a14da9be42c0c477c4ae15a8e9171d11ae68ea5fc77889042a2a1e9990",
        "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a525.html",
        "motor_vehicle_dealers_act_1973_consolidated_06-k0-01.pdf",
    ),
    "owner_drivers_contracts_and_disputes_act_2007": (
        "owner_drivers_contracts_and_disputes_act_2007",
        "Owner-Drivers (Contracts and Disputes) Act 2007",
        "01-g0-00",
        "007 of 2007",
        date(2025, 1, 31),
        date(2025, 1, 31),
        datetime(2026, 9, 8, 4, 19, 20, tzinfo=UTC),
        "03071c9fe15dfdc3a8c26ebfd9027f5ff6044f91c83e0455ace5b5ac40b43bad",
        "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a146614.html",
        "owner_drivers_contracts_and_disputes_act_2007_consolidated_01-g0-00.pdf",
    ),
}

# (act_dir, act_title, identifier, pinpoint, heading)
_PINNED_PROVISIONS = [
    (
        "building_and_construction_industry_security_of_payment_act_2021",
        "Building and Construction Industry (Security of Payment) Act 2021",
        "s 17",
        "section 17",
        "Right to progress payments",
    ),
    (
        "building_and_construction_industry_security_of_payment_act_2021",
        "Building and Construction Industry (Security of Payment) Act 2021",
        "s 18",
        "section 18",
        "Amount of progress payment",
    ),
    (
        "building_and_construction_industry_security_of_payment_act_2021",
        "Building and Construction Industry (Security of Payment) Act 2021",
        "s 22",
        "section 22",
        "Making payment claims",
    ),
    (
        "building_and_construction_industry_security_of_payment_act_2021",
        "Building and Construction Industry (Security of Payment) Act 2021",
        "s 25",
        "section 25",
        "Response to payment claim: payment schedule",
    ),
    (
        "motor_vehicle_dealers_act_1973",
        "Motor Vehicle Dealers Act 1973",
        "s 5",
        "section 5",
        "Terms used",
    ),
    (
        "motor_vehicle_dealers_act_1973",
        "Motor Vehicle Dealers Act 1973",
        "s 5A",
        "section 5A",
        "Classes of business and categories of licence",
    ),
    (
        "motor_vehicle_dealers_act_1973",
        "Motor Vehicle Dealers Act 1973",
        "s 15",
        "section 15",
        "Vehicle dealer\u2019s licence, application for and grant of",
    ),
    (
        "motor_vehicle_dealers_act_1973",
        "Motor Vehicle Dealers Act 1973",
        "s 30",
        "section 30",
        "Unlicensed dealing etc., offences as to",
    ),
    (
        "owner_drivers_contracts_and_disputes_act_2007",
        "Owner-Drivers (Contracts and Disputes) Act 2007",
        "s 4",
        "section 4",
        "Term used: owner-driver",
    ),
    (
        "owner_drivers_contracts_and_disputes_act_2007",
        "Owner-Drivers (Contracts and Disputes) Act 2007",
        "s 6",
        "section 6",
        "Application of Act",
    ),
    (
        "owner_drivers_contracts_and_disputes_act_2007",
        "Owner-Drivers (Contracts and Disputes) Act 2007",
        "s 7",
        "section 7",
        "Act prevails over owner-driver contracts",
    ),
]

# (act_dir, act_title, identifier, pinpoint) for the derivation-digest checks.
_PINNED_DIGESTS = [(row[0], row[1], row[2], row[3]) for row in _PINNED_PROVISIONS]


def _service() -> WaResearchService:
    return WaResearchService(
        corpus=RecordedWaCorpus(RECORDED_FIXTURE_ROOT),
        audit_sink=InMemoryResearchAuditSink(),
    )


@pytest.mark.parametrize(
    ("act_dir", "act_title", "identifier", "pinpoint", "heading"),
    _PINNED_PROVISIONS,
    ids=[f"{row[0]}-{row[2]}".replace(" ", "-") for row in _PINNED_PROVISIONS],
)
def test_each_recorded_pinned_provision_yields_a_complete_validated_packet(
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
    list(_RECORDS),
    ids=[act_dir for act_dir in _RECORDS],
)
def test_recorded_corpus_slice_fixtures_have_unmodified_recorded_bytes(act_dir: str) -> None:
    record = _RECORDS[act_dir]

    on_disk = (RECORDED_FIXTURE_ROOT / act_dir / record[9]).read_bytes()

    assert hashlib.sha256(on_disk).hexdigest() == record[7]


@pytest.mark.parametrize(
    "act_title",
    [record[1] for record in _RECORDS.values()],
    ids=[act_dir for act_dir in _RECORDS],
)
def test_recorded_corpus_slice_fixtures_are_selected_by_title_exactly_once(act_title: str) -> None:
    corpus = RecordedWaCorpus(RECORDED_FIXTURE_ROOT)

    source = corpus.select(recorded_query(act_title=act_title))

    # A second recorded source with the same title would make this raise
    # AmbiguousSelection rather than guess, so a single non-None result
    # proves the title matches exactly once.
    assert source is not None
    assert source.act_title == act_title
    assert source.source_system == "wa_legislation"
    assert source.jurisdiction == "WA"


def _slug(identifier: str) -> str:
    return identifier.replace(" ", "_").replace(".", "")


def _packet_sha256(act_title: str, identifier: str, pinpoint: str) -> str:
    result = _service().research(
        recorded_query(act_title=act_title, provision_identifier=identifier, pinpoint=pinpoint)
    )
    assert isinstance(result, ResearchValidated)
    sha256 = result.packet.sha256
    assert isinstance(sha256, str)
    return sha256


@pytest.mark.parametrize(
    ("act_dir", "act_title", "identifier", "pinpoint"),
    _PINNED_DIGESTS,
    ids=[f"{row[0]}-{row[2]}".replace(" ", "-") for row in _PINNED_DIGESTS],
)
def test_derived_provision_digest_matches_the_source_packet_digest(
    act_dir: str, act_title: str, identifier: str, pinpoint: str
) -> None:
    record_path = (
        RECORDED_FIXTURE_ROOT / act_dir / "provisions" / f"{_slug(identifier)}.provision.json"
    )
    text_path = record_path.with_name(f"{_slug(identifier)}.txt")

    assert record_path.is_file()
    assert text_path.is_file()
    assert text_path.stat().st_size > 0

    record = json.loads(record_path.read_text(encoding="utf-8"))
    text = text_path.read_bytes()
    manifest_path = next((RECORDED_FIXTURE_ROOT / act_dir).glob("*.manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert record["parent_sha256"] == _packet_sha256(act_title, identifier, pinpoint)
    assert record["source_version"] == manifest["version"]["suffix"]
    assert record["sha256"] == hashlib.sha256(text).hexdigest()
    assert record["byte_length"] == len(text)
    assert record["provision_identifier"] == identifier
    assert record["pinpoint"] == pinpoint
    assert text.strip()


def _collapse(value: str) -> str:
    """Return the text with every run of whitespace reduced to one space."""

    return " ".join(value.split())


def _document_text(pdf_path: Path) -> str:
    """Return the whole source document exactly as the derivation pipeline sees it.

    The derivation pipeline removes repeated page furniture first
    (``_document_lines``) and operates on that view; the same view is used here
    so a derived provision unit must trace back to contiguous source lines.
    """

    return NEWLINE.join(_document_lines(pdf_path))


@pytest.mark.parametrize(
    ("act_dir", "act_title", "identifier", "pinpoint"),
    _PINNED_DIGESTS,
    ids=[f"{row[0]}-{row[2]}".replace(" ", "-") for row in _PINNED_DIGESTS],
)
def test_derived_provision_text_units_are_substrings_of_the_source_document(
    act_dir: str, act_title: str, identifier: str, pinpoint: str
) -> None:
    text_path = RECORDED_FIXTURE_ROOT / act_dir / "provisions" / f"{_slug(identifier)}.txt"

    provision = text_path.read_text(encoding="utf-8")
    assert provision.strip()

    pdf_path = next((RECORDED_FIXTURE_ROOT / act_dir).glob("*.pdf"))
    document = _collapse(_document_text(pdf_path.resolve()))
    assert document

    for unit in provision.splitlines():
        collapsed = _collapse(unit)
        if collapsed:
            assert collapsed in document

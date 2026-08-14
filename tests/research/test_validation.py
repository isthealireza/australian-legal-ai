"""Unit tests for deterministic WA evidence-packet validation."""

from __future__ import annotations

import hashlib
from datetime import date

import pytest
from pydantic import ValidationError

from legal_ai.research.models import PacketDraft, RecordedProvision
from legal_ai.research.types import LegalStatus, ResearchRefusalCode
from legal_ai.research.validation import validate_recorded_source
from tests.research.conftest import (
    SYNTHETIC_CONTENT,
    SYNTHETIC_SHA256,
    query,
    recorded_source,
)

_OTHER_DIGEST = hashlib.sha256(b"a different document").hexdigest()


def test_valid_source_yields_every_required_packet_field() -> None:
    result = validate_recorded_source(query(), recorded_source())

    assert isinstance(result, PacketDraft)
    assert result.source_id == "wa_legislation:synthetic_act_1974:consolidated:1-a0-00"
    assert result.act_title == "Synthetic Act 1974"
    assert result.act_number == "001 of 1974"
    assert result.provision_identifier == "s 55"
    assert result.pinpoint == "section 55"
    assert result.provision_heading == "Synthetic heading"
    assert result.source_version == "1-a0-00"
    assert result.compilation_date == date(2025, 1, 10)
    assert result.legal_status is LegalStatus.IN_FORCE
    assert result.status_date == date(2025, 1, 10)
    assert result.source_content == SYNTHETIC_CONTENT
    assert result.retrieved_at.utcoffset() is not None
    assert result.sha256 == SYNTHETIC_SHA256


def test_packet_carries_recorded_values_not_requested_values() -> None:
    result = validate_recorded_source(
        query(provision_identifier="SECTION 55", pinpoint="Section  55"),
        recorded_source(),
    )

    assert isinstance(result, PacketDraft)
    assert result.provision_identifier == "s 55"
    assert result.pinpoint == "section 55"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"source_system": None}, ResearchRefusalCode.FIELD_MISSING),
        ({"source_system": "   "}, ResearchRefusalCode.FIELD_MISSING),
        ({"source_system": "federal_register"}, ResearchRefusalCode.SOURCE_SYSTEM_MISMATCH),
        ({"source_system": "wa_courts"}, ResearchRefusalCode.SOURCE_SYSTEM_MISMATCH),
        ({"jurisdiction": None}, ResearchRefusalCode.FIELD_MISSING),
        ({"jurisdiction": "NSW"}, ResearchRefusalCode.JURISDICTION_MISMATCH),
        ({"jurisdiction": "wa"}, ResearchRefusalCode.JURISDICTION_MISMATCH),
        ({"act_jurisdiction": "NSW"}, ResearchRefusalCode.JURISDICTION_MISMATCH),
        ({"act_jurisdiction": None}, ResearchRefusalCode.FIELD_MISSING),
        ({"source_id": None}, ResearchRefusalCode.FIELD_MISSING),
        ({"source_id": ""}, ResearchRefusalCode.FIELD_MISSING),
        ({"act_title": None}, ResearchRefusalCode.FIELD_MISSING),
        ({"official_source_url": None}, ResearchRefusalCode.FIELD_MISSING),
        ({"status_date": None}, ResearchRefusalCode.FIELD_MISSING),
        ({"retrieved_at": None}, ResearchRefusalCode.FIELD_MISSING),
        ({"sha256": None}, ResearchRefusalCode.FIELD_MISSING),
        ({"source_content": b""}, ResearchRefusalCode.FIELD_MISSING),
    ],
)
def test_missing_or_mismatched_identity_fields_refuse(
    overrides: dict[str, object], expected: ResearchRefusalCode
) -> None:
    assert validate_recorded_source(query(), recorded_source(**overrides)) is expected


@pytest.mark.parametrize(
    "url",
    [
        "https://legislation.wa.gov.au/legislation/statutes.nsf/law_s1.html",
        "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_s1.html",
        "https://www.legislation.wa.gov.au:443/legislation/statutes.nsf/law_s1.html",
    ],
)
def test_closed_two_host_allowlist_accepts_only_the_recorded_wa_hosts(url: str) -> None:
    result = validate_recorded_source(query(), recorded_source(official_source_url=url))

    assert isinstance(result, PacketDraft)
    assert result.official_source_url == url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "http://www.legislation.wa.gov.au/legislation/statutes.nsf/law_s1.html",
            ResearchRefusalCode.SOURCE_NOT_ALLOWLISTED,
        ),
        (
            "https://legislation.wa.gov.au.attacker.example/law_s1.html",
            ResearchRefusalCode.SOURCE_NOT_ALLOWLISTED,
        ),
        (
            "https://mirror.legislation.wa.gov.au/law_s1.html",
            ResearchRefusalCode.SOURCE_NOT_ALLOWLISTED,
        ),
        (
            "https://legislation.nsw.gov.au/law_s1.html",
            ResearchRefusalCode.SOURCE_NOT_ALLOWLISTED,
        ),
        (
            "https://user:secret@www.legislation.wa.gov.au/law_s1.html",
            ResearchRefusalCode.SOURCE_NOT_ALLOWLISTED,
        ),
        (
            "https://www.legislation.wa.gov.au:8443/law_s1.html",
            ResearchRefusalCode.SOURCE_NOT_ALLOWLISTED,
        ),
        ("ftp://www.legislation.wa.gov.au/law_s1.html", ResearchRefusalCode.SOURCE_NOT_ALLOWLISTED),
        ("https://[oops/law_s1.html", ResearchRefusalCode.FIELD_INVALID),
        (" https://www.legislation.wa.gov.au/law_s1.html", ResearchRefusalCode.FIELD_INVALID),
        ("https://www.legislation.wa.gov.au/law\n_s1.html", ResearchRefusalCode.FIELD_INVALID),
    ],
)
def test_non_allowlisted_or_malformed_urls_refuse(url: str, expected: ResearchRefusalCode) -> None:
    assert validate_recorded_source(query(), recorded_source(official_source_url=url)) is expected


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"source_version": None, "compilation_date": None}, ResearchRefusalCode.VERSION_MISSING),
        (
            {"source_version": "UNKNOWN", "compilation_date": "unknown"},
            ResearchRefusalCode.VERSION_MISSING,
        ),
        (
            {"source_version": "  ", "compilation_date": None},
            ResearchRefusalCode.VERSION_MISSING,
        ),
        (
            {"source_version": "1-a0-00", "compilation_date": "10 January 2025"},
            ResearchRefusalCode.FIELD_INVALID,
        ),
        (
            {"source_version": None, "compilation_date": "2025-13-45"},
            ResearchRefusalCode.FIELD_INVALID,
        ),
    ],
)
def test_missing_or_invalid_version_and_compilation_date_refuse(
    overrides: dict[str, object], expected: ResearchRefusalCode
) -> None:
    assert validate_recorded_source(query(), recorded_source(**overrides)) is expected


@pytest.mark.parametrize(
    "overrides",
    [
        {"source_version": "1-a0-00", "compilation_date": None},
        {"source_version": None, "compilation_date": "2025-01-10"},
    ],
)
def test_either_exact_version_or_compilation_date_satisfies_the_field(
    overrides: dict[str, object],
) -> None:
    assert isinstance(validate_recorded_source(query(), recorded_source(**overrides)), PacketDraft)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"status_currency": None}, ResearchRefusalCode.STATUS_UNKNOWN),
        ({"status_currency": "UNKNOWN"}, ResearchRefusalCode.STATUS_UNKNOWN),
        ({"status_currency": "probably current"}, ResearchRefusalCode.STATUS_UNKNOWN),
        ({"status_in_force": None}, ResearchRefusalCode.STATUS_UNKNOWN),
        ({"status_in_force": False}, ResearchRefusalCode.STATUS_UNKNOWN),
        (
            {"status_currency": "Repealed", "status_in_force": True},
            ResearchRefusalCode.STATUS_UNKNOWN,
        ),
        ({"status_date": "2025-02-30"}, ResearchRefusalCode.STATUS_DATE_INVALID),
        ({"status_date": "10 January 2025"}, ResearchRefusalCode.STATUS_DATE_INVALID),
        ({"status_date": "2026-08-12"}, ResearchRefusalCode.STATUS_DATE_INVALID),
    ],
)
def test_unknown_status_or_wrong_status_date_refuses(
    overrides: dict[str, object], expected: ResearchRefusalCode
) -> None:
    assert validate_recorded_source(query(), recorded_source(**overrides)) is expected


def test_repealed_status_is_a_known_status() -> None:
    result = validate_recorded_source(
        query(), recorded_source(status_currency="Repealed", status_in_force=False)
    )

    assert isinstance(result, PacketDraft)
    assert result.legal_status is LegalStatus.REPEALED


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"retrieved_at": "2026-08-11T10:27:03"}, ResearchRefusalCode.FIELD_INVALID),
        ({"retrieved_at": "2026-08-11T10:27:03+08:00"}, ResearchRefusalCode.FIELD_INVALID),
        ({"retrieved_at": "11 August 2026"}, ResearchRefusalCode.FIELD_INVALID),
        ({"sha256": SYNTHETIC_SHA256.upper()}, ResearchRefusalCode.FIELD_INVALID),
        ({"sha256": SYNTHETIC_SHA256[:63]}, ResearchRefusalCode.FIELD_INVALID),
        ({"sha256": "z" * 64}, ResearchRefusalCode.FIELD_INVALID),
        ({"sha256": _OTHER_DIGEST}, ResearchRefusalCode.HASH_MISMATCH),
        ({"source_content": b"tampered content"}, ResearchRefusalCode.HASH_MISMATCH),
    ],
)
def test_invalid_timestamps_and_digests_refuse(
    overrides: dict[str, object], expected: ResearchRefusalCode
) -> None:
    assert validate_recorded_source(query(), recorded_source(**overrides)) is expected


def test_sha256_is_recomputed_against_the_exact_source_content() -> None:
    content = b"exact recorded bytes"
    result = validate_recorded_source(
        query(),
        recorded_source(source_content=content, sha256=hashlib.sha256(content).hexdigest()),
    )

    assert isinstance(result, PacketDraft)
    assert result.sha256 == hashlib.sha256(result.source_content).hexdigest()


@pytest.mark.parametrize("requested", ["s 99", "section 99", "s 55A", "s 5", "55"])
def test_citation_existence_refuses_provisions_absent_from_the_corpus(requested: str) -> None:
    result = validate_recorded_source(query(provision_identifier=requested), recorded_source())

    assert result is ResearchRefusalCode.CITATION_NOT_FOUND


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_query_contract_rejects_blank_provision_identifiers(blank: str) -> None:
    with pytest.raises(ValidationError):
        query(provision_identifier=blank)


def test_citation_existence_refuses_when_no_provisions_were_recorded() -> None:
    result = validate_recorded_source(query(), recorded_source(provisions=()))

    assert result is ResearchRefusalCode.CITATION_NOT_FOUND


@pytest.mark.parametrize("pinpoint", ["section 56", "s 55", "section 55(2)", "sections 55 and 56"])
def test_pinpoint_integrity_refuses_any_pinpoint_but_the_recorded_one(pinpoint: str) -> None:
    result = validate_recorded_source(query(pinpoint=pinpoint), recorded_source())

    assert result is ResearchRefusalCode.PINPOINT_MISMATCH


def test_pinpoint_integrity_accepts_the_exact_recorded_pinpoint() -> None:
    source = recorded_source(
        provisions=(
            RecordedProvision(identifier="s 56", pinpoint="section 56", heading="Other heading"),
        )
    )
    result = validate_recorded_source(
        query(provision_identifier="s 56", pinpoint="section 56"), source
    )

    assert isinstance(result, PacketDraft)
    assert result.pinpoint == "section 56"


def test_validation_is_deterministic_across_repeated_execution() -> None:
    source = recorded_source()
    results = [validate_recorded_source(query(), source) for _ in range(5)]

    assert all(isinstance(result, PacketDraft) for result in results)
    assert len({repr(result) for result in results}) == 1

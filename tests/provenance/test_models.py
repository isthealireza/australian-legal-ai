from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from legal_ai.provenance import FederalRegisterCapture


def _capture_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "source_system": "federal_register",
        "title_id": "C2004A00109",
        "register_id": "C2026C00206",
        "official_document_id": "C2026C00206-primary-pdf-volume-1",
        "official_source_url": (
            "https://api.prod.legislation.gov.au/v1/documents/C2026C00206-primary-pdf-volume-1"
        ),
        "document_format": "Pdf",
        "volume": 1,
        "response_content_type": "application/pdf; charset=binary",
        "retrieved_at": datetime(2026, 7, 21, 3, 4, 5, tzinfo=UTC),
        "etag": 'W/"raw-etag"',
        "last_modified": "Tue, 21 Jul 2026 03:04:05 GMT",
        "expected_sha256": "a" * 64,
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_system", "other"),
        ("title_id", 123),
        ("title_id", "malformed"),
        ("register_id", "malformed"),
        ("official_document_id", ""),
        ("document_format", "PDF"),
        ("volume", 1.0),
        ("response_content_type", ""),
        ("expected_sha256", "A" * 64),
    ],
)
def test_provenance_model_is_strict(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        FederalRegisterCapture.model_validate(_capture_data(**{field: value}))


def test_provenance_model_forbids_arbitrary_metadata() -> None:
    with pytest.raises(ValidationError):
        FederalRegisterCapture.model_validate(_capture_data(metadata={"unbounded": True}))


def test_non_https_url_is_rejected() -> None:
    with pytest.raises(ValidationError, match="HTTPS"):
        FederalRegisterCapture.model_validate(
            _capture_data(
                official_source_url=("http://api.prod.legislation.gov.au/v1/documents/document-id")
            )
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/document",
        "https://api.prod.legislation.gov.au.evil.example/document",
        "https://www.legislation.gov.au/document",
        "https://api.prod.legislation.gov.au:444/document",
    ],
)
def test_non_approved_host_or_port_is_rejected(url: str) -> None:
    with pytest.raises(ValidationError, match="approved"):
        FederalRegisterCapture.model_validate(_capture_data(official_source_url=url))


def test_both_documented_official_hosts_are_approved() -> None:
    api_capture = FederalRegisterCapture.model_validate(_capture_data())
    site_capture = FederalRegisterCapture.model_validate(
        _capture_data(official_source_url="https://legislation.gov.au/document/id")
    )

    assert api_capture.official_source_url.startswith("https://api.prod.")
    assert site_capture.official_source_url == "https://legislation.gov.au/document/id"


def test_timezone_naive_retrieval_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        FederalRegisterCapture.model_validate(
            _capture_data(retrieved_at=datetime(2026, 7, 21, 3, 4, 5))
        )


def test_non_utc_retrieval_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        FederalRegisterCapture.model_validate(
            _capture_data(retrieved_at=datetime.fromisoformat("2026-07-21T11:04:05+08:00"))
        )


def test_retrieval_timestamp_defaults_to_system_utc() -> None:
    data = _capture_data()
    del data["retrieved_at"]

    capture = FederalRegisterCapture.model_validate(data)

    assert capture.retrieved_at.utcoffset() == UTC.utcoffset(capture.retrieved_at)


def test_raw_etag_and_last_modified_are_preserved_exactly() -> None:
    capture = FederalRegisterCapture.model_validate(
        _capture_data(
            etag='W/"Case-Sensitive, raw"',
            last_modified="not normalized by this boundary",
        )
    )

    assert capture.etag == 'W/"Case-Sensitive, raw"'
    assert capture.last_modified == "not normalized by this boundary"

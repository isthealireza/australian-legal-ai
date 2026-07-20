import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest

from legal_ai.sources.frl import FederalRegisterClient

_FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "frl"
_RECORDED_CONTENT_TYPE = (
    "application/json; odata.metadata=minimal; odata.streaming=true; charset=utf-8"
)
_PILOTS = [
    (
        "privacy_act_1988",
        "C2004A03712",
        "C2026C00227",
        "104",
        3,
    ),
    (
        "competition_and_consumer_act_2010",
        "C2004A00109",
        "C2026C00206",
        "164",
        9,
    ),
]
_RETRIEVAL_TIMES = {
    ("privacy_act_1988", "title"): "2026-07-20T16:49:10.6828860+00:00",
    ("privacy_act_1988", "version"): "2026-07-20T16:49:54.3141082+00:00",
    ("privacy_act_1988", "documents"): "2026-07-20T16:50:05.4001982+00:00",
    (
        "competition_and_consumer_act_2010",
        "title",
    ): "2026-07-20T16:49:11.9959920+00:00",
    (
        "competition_and_consumer_act_2010",
        "version",
    ): "2026-07-20T16:50:13.0492025+00:00",
    (
        "competition_and_consumer_act_2010",
        "documents",
    ): "2026-07-20T16:50:23.6562876+00:00",
}


def _fixture_transport(path: Path) -> httpx.MockTransport:
    body = path.read_bytes()
    manifest_path = path.with_name(f"{path.stem}.manifest.json")
    manifest = cast(dict[str, object], json.loads(manifest_path.read_bytes()))
    content_type = cast(str, manifest["content_type"])

    def handler(request: httpx.Request) -> httpx.Response:
        response = httpx.Response(
            200,
            headers={"Content-Type": content_type},
            stream=httpx.ByteStream(body),
        )
        assert "Content-Length" not in response.headers
        return response

    return httpx.MockTransport(handler)


@pytest.mark.parametrize(
    ("fixture_directory", "title_id", "register_id", "compilation_number", "document_count"),
    _PILOTS,
)
def test_recorded_title_fixture_matches_contract(
    fixture_directory: str,
    title_id: str,
    register_id: str,
    compilation_number: str,
    document_count: int,
) -> None:
    path = _FIXTURE_ROOT / fixture_directory / "title.json"
    with FederalRegisterClient(transport=_fixture_transport(path)) as client:
        title = client.get_title(title_id)

    assert title.title_id == title_id


@pytest.mark.parametrize(
    ("fixture_directory", "title_id", "register_id", "compilation_number", "document_count"),
    _PILOTS,
)
def test_recorded_version_fixture_matches_contract(
    fixture_directory: str,
    title_id: str,
    register_id: str,
    compilation_number: str,
    document_count: int,
) -> None:
    path = _FIXTURE_ROOT / fixture_directory / "version.json"
    with FederalRegisterClient(transport=_fixture_transport(path)) as client:
        version = client.get_latest_registered_version(title_id)

    assert version.title_id == title_id
    assert version.register_id == register_id
    assert version.compilation_number == compilation_number


def test_recorded_competition_version_preserves_latest_not_current_semantics() -> None:
    path = _FIXTURE_ROOT / "competition_and_consumer_act_2010" / "version.json"
    with FederalRegisterClient(transport=_fixture_transport(path)) as client:
        version = client.get_latest_registered_version("C2004A00109")

    assert version.is_latest is True
    assert version.is_current is False
    assert version.end == "2026-07-01T00:00:00"


@pytest.mark.parametrize(
    ("fixture_directory", "title_id", "register_id", "compilation_number", "document_count"),
    _PILOTS,
)
def test_recorded_document_fixture_matches_contract(
    fixture_directory: str,
    title_id: str,
    register_id: str,
    compilation_number: str,
    document_count: int,
) -> None:
    path = _FIXTURE_ROOT / fixture_directory / "documents.json"
    with FederalRegisterClient(transport=_fixture_transport(path)) as client:
        documents = client.list_documents(register_id)

    assert len(documents) == document_count
    assert {document.title_id for document in documents} == {title_id}
    assert {document.register_id for document in documents} == {register_id}
    assert {document.compilation_number for document in documents} == {compilation_number}


_MANIFEST_CASES = [
    (fixture_directory, response_name, title_id, register_id, compilation_number)
    for fixture_directory, title_id, register_id, compilation_number, _ in _PILOTS
    for response_name in ("title", "version", "documents")
]


@pytest.mark.parametrize(
    ("fixture_directory", "response_name", "title_id", "register_id", "compilation_number"),
    _MANIFEST_CASES,
)
def test_recorded_fixture_manifest_preserves_capture_provenance(
    fixture_directory: str,
    response_name: str,
    title_id: str,
    register_id: str,
    compilation_number: str,
) -> None:
    directory = _FIXTURE_ROOT / fixture_directory
    fixture_bytes = (directory / f"{response_name}.json").read_bytes()
    manifest = cast(
        dict[str, object],
        json.loads((directory / f"{response_name}.manifest.json").read_bytes()),
    )
    request = cast(dict[str, object], manifest["request"])
    retrieved_at = datetime.fromisoformat(cast(str, manifest["retrieved_at_utc"]))

    assert set(manifest) == {
        "request",
        "retrieved_at_utc",
        "http_status",
        "content_type",
        "etag",
        "last_modified",
        "content_length",
        "content_digest",
        "repr_digest",
        "sha256",
        "title_id",
        "register_id",
        "compilation_number",
    }
    assert set(request) == {"method", "url", "parameters"}
    assert request["method"] == "GET"
    if response_name == "title":
        assert request["url"] == (f"https://api.prod.legislation.gov.au/v1/titles('{title_id}')")
        assert request["parameters"] == {}
    elif response_name == "version":
        assert request["url"] == "https://api.prod.legislation.gov.au/v1/versions"
        assert request["parameters"] == {"$filter": f"titleId eq '{title_id}' and isLatest eq true"}
    else:
        assert request["url"] == "https://api.prod.legislation.gov.au/v1/documents"
        assert request["parameters"] == {"$filter": f"registerId eq '{register_id}'"}
    assert manifest["retrieved_at_utc"] == _RETRIEVAL_TIMES[(fixture_directory, response_name)]
    assert manifest["http_status"] == 200
    assert manifest["content_type"] == _RECORDED_CONTENT_TYPE
    for header_name in (
        "etag",
        "last_modified",
        "content_length",
        "content_digest",
        "repr_digest",
    ):
        assert manifest[header_name] is None
    assert retrieved_at.utcoffset() == UTC.utcoffset(retrieved_at)
    assert manifest["title_id"] == title_id
    assert manifest["register_id"] == register_id
    assert manifest["compilation_number"] == compilation_number
    assert hashlib.sha256(fixture_bytes).hexdigest() == manifest["sha256"]

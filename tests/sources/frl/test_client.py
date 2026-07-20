import json
from collections.abc import Iterator
from datetime import datetime

import httpx
import pytest
from pydantic import ValidationError

from legal_ai.sources.frl import (
    FederalRegisterClient,
    FederalRegisterRedirectError,
    FederalRegisterRequestError,
    FederalRegisterResponseError,
    TitleMetadata,
)


def _title_response_body(size: int) -> bytes:
    payload = json.dumps(
        {
            "id": "C2004A03712",
            "name": "Privacy Act 1988",
            "makingDate": "1988-12-14T00:00:00",
            "collection": "Act",
            "isPrincipal": True,
            "isInForce": True,
            "status": "InForce",
            "hasCommencedUnincorporatedAmendments": False,
        },
        separators=(",", ":"),
    ).encode()
    if len(payload) > size:
        raise ValueError("requested body size is too small")
    return payload + (b" " * (size - len(payload)))


def _version_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "titleId": "C2004A00109",
        "start": "2026-05-27T00:00:00",
        "end": "2026-07-01T00:00:00",
        "isCurrent": False,
        "isLatest": True,
        "name": "Competition and Consumer Act 2010",
        "status": "InForce",
        "registerId": "C2026C00206",
        "registeredAt": "2026-05-28T16:57:25.7089337",
        "compilationNumber": "164",
        "hasUnincorporatedAmendments": False,
    }
    payload.update(overrides)
    return payload


class RecordingByteStream(httpx.SyncByteStream):
    def __init__(self, *chunks: bytes) -> None:
        self._chunks = chunks
        self.chunks_yielded = 0

    def __iter__(self) -> Iterator[bytes]:
        for chunk in self._chunks:
            self.chunks_yielded += 1
            yield chunk


def test_get_title_validates_official_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "api.prod.legislation.gov.au"
        assert request.url.path == "/v1/titles('C2004A03712')"
        assert request.url.query == b""
        assert request.headers["User-Agent"] == "australian-legal-ai-research-prototype/0.1"
        return httpx.Response(
            200,
            headers={
                "Content-Type": (
                    "application/json; odata.metadata=minimal; odata.streaming=true; charset=utf-8"
                )
            },
            json={
                "id": "C2004A03712",
                "name": "Privacy Act 1988",
                "makingDate": "1988-12-14T00:00:00",
                "collection": "Act",
                "isPrincipal": True,
                "isInForce": True,
                "status": "InForce",
                "hasCommencedUnincorporatedAmendments": False,
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        title = client.get_title("C2004A03712")

    assert title.title_id == "C2004A03712"
    assert title.name == "Privacy Act 1988"
    assert title.making_date == "1988-12-14T00:00:00"
    assert title.model_dump(by_alias=True)["makingDate"] == "1988-12-14T00:00:00"
    assert title.collection == "Act"
    assert title.status == "InForce"


def test_get_title_preserves_offset_bearing_timestamp_exactly() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "id": "C2004A03712",
                "name": "Privacy Act 1988",
                "makingDate": "1988-12-14T10:30:00.1234567+10:30",
                "collection": "Act",
                "isPrincipal": True,
                "isInForce": True,
                "status": "InForce",
                "hasCommencedUnincorporatedAmendments": False,
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        title = client.get_title("C2004A03712")

    assert title.making_date == "1988-12-14T10:30:00.1234567+10:30"


def test_title_transport_model_rejects_python_datetime_timestamp() -> None:
    with pytest.raises(ValidationError):
        TitleMetadata.model_validate(
            {
                "id": "C2004A03712",
                "name": "Privacy Act 1988",
                "makingDate": datetime(1988, 12, 14),
                "collection": "Act",
                "isPrincipal": True,
                "isInForce": True,
                "status": "InForce",
                "hasCommencedUnincorporatedAmendments": False,
            }
        )


def test_get_latest_registered_version_validates_version_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "api.prod.legislation.gov.au"
        assert request.url.path == "/v1/versions"
        assert request.url.params["$filter"] == ("titleId eq 'C2004A00109' and isLatest eq true")
        assert request.url.query == (b"%24filter=titleId+eq+%27C2004A00109%27+and+isLatest+eq+true")
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "value": [
                    {
                        "titleId": "C2004A00109",
                        "start": "2026-05-27T00:00:00",
                        "end": "2026-07-01T00:00:00",
                        "isCurrent": False,
                        "isLatest": True,
                        "name": "Competition and Consumer Act 2010",
                        "status": "InForce",
                        "registerId": "C2026C00206",
                        "registeredAt": "2026-05-28T16:57:25.7089337",
                        "compilationNumber": "164",
                        "hasUnincorporatedAmendments": False,
                    }
                ]
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        version = client.get_latest_registered_version("C2004A00109")

    assert version.title_id == "C2004A00109"
    assert version.register_id == "C2026C00206"
    assert version.compilation_number == "164"
    assert version.is_latest is True
    assert version.is_current is False
    assert version.start == "2026-05-27T00:00:00"
    assert version.end == "2026-07-01T00:00:00"
    assert version.registered_at == "2026-05-28T16:57:25.7089337"
    assert version.model_dump(by_alias=True)["registeredAt"] == "2026-05-28T16:57:25.7089337"


def test_get_latest_registered_version_rejects_result_not_marked_latest() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "value": [
                    {
                        "titleId": "C2004A00109",
                        "start": "2026-05-27T00:00:00",
                        "end": "2026-07-01T00:00:00",
                        "isCurrent": False,
                        "isLatest": False,
                        "name": "Competition and Consumer Act 2010",
                        "status": "InForce",
                        "registerId": "C2026C00206",
                        "registeredAt": "2026-05-28T16:57:25.7089337",
                        "compilationNumber": "164",
                        "hasUnincorporatedAmendments": False,
                    }
                ]
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="not marked latest"):
            client.get_latest_registered_version("C2004A00109")


def test_get_latest_registered_version_rejects_continuation_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "@odata.nextLink": "https://api.prod.legislation.gov.au/v1/versions?$skip=1",
                "value": [
                    {
                        "titleId": "C2004A00109",
                        "start": "2026-05-27T00:00:00",
                        "end": "2026-07-01T00:00:00",
                        "isCurrent": False,
                        "isLatest": True,
                        "name": "Competition and Consumer Act 2010",
                        "status": "InForce",
                        "registerId": "C2026C00206",
                        "registeredAt": "2026-05-28T16:57:25.7089337",
                        "compilationNumber": "164",
                        "hasUnincorporatedAmendments": False,
                    }
                ],
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="continuation"):
            client.get_latest_registered_version("C2004A00109")


def test_get_latest_registered_version_rejects_malformed_continuation_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={"@odata.nextLink": 123, "value": []},
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="failed validation"):
            client.get_latest_registered_version("C2004A00109")


def test_get_latest_registered_version_rejects_empty_collection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={"value": []},
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="exactly one result"):
            client.get_latest_registered_version("C2004A00109")


def test_get_latest_registered_version_rejects_multiple_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={"value": [_version_payload(), _version_payload()]},
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="exactly one result"):
            client.get_latest_registered_version("C2004A00109")


def test_list_documents_validates_document_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/documents"
        assert request.url.params["$filter"] == "registerId eq 'C2026C00227'"
        assert request.url.query == b"%24filter=registerId+eq+%27C2026C00227%27"
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "value": [
                    {
                        "titleId": "C2004A03712",
                        "start": "2026-06-04T00:00:00",
                        "rectificationVersionNumber": 0,
                        "type": "Primary",
                        "uniqueTypeNumber": 0,
                        "volumeNumber": 0,
                        "format": "Pdf",
                        "compilationNumber": "104",
                        "registerId": "C2026C00227",
                        "extension": ".pdf",
                        "pageCount": 472,
                        "sizeInBytes": 1920725,
                        "isAuthorised": True,
                        "contents": None,
                    }
                ]
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        documents = client.list_documents("C2026C00227")

    assert len(documents) == 1
    assert documents[0].register_id == "C2026C00227"
    assert documents[0].start == "2026-06-04T00:00:00"
    assert documents[0].format == "Pdf"
    assert documents[0].volume_number == 0
    assert documents[0].is_authorised is True


def test_list_documents_rejects_continuation_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "@odata.nextLink": "https://api.prod.legislation.gov.au/v1/documents?$skip=1",
                "value": [
                    {
                        "titleId": "C2004A03712",
                        "start": "2026-06-04T00:00:00",
                        "rectificationVersionNumber": 0,
                        "type": "Primary",
                        "uniqueTypeNumber": 0,
                        "volumeNumber": 0,
                        "format": "Pdf",
                        "compilationNumber": "104",
                        "registerId": "C2026C00227",
                        "extension": ".pdf",
                        "pageCount": 472,
                        "sizeInBytes": 1920725,
                        "isAuthorised": True,
                        "contents": None,
                    }
                ],
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="continuation"):
            client.list_documents("C2026C00227")


def test_list_documents_rejects_response_register_identifier_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "value": [
                    {
                        "titleId": "C2004A00109",
                        "start": "2026-05-27T00:00:00",
                        "rectificationVersionNumber": 0,
                        "type": "Primary",
                        "uniqueTypeNumber": 0,
                        "volumeNumber": 1,
                        "format": "Pdf",
                        "compilationNumber": "164",
                        "registerId": "C2026C00206",
                        "extension": ".pdf",
                        "pageCount": 549,
                        "sizeInBytes": 2192524,
                        "isAuthorised": True,
                        "contents": None,
                    }
                ]
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="identifier did not match"):
            client.list_documents("C2026C00227")


def test_list_documents_preserves_multi_volume_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        documents = []
        for volume_number, contents in ((1, "s 1-53ZZC"), (4, "sch 1-Endnotes")):
            documents.append(
                {
                    "titleId": "C2004A00109",
                    "start": "2026-05-27T00:00:00",
                    "rectificationVersionNumber": 0,
                    "type": "Primary",
                    "uniqueTypeNumber": 0,
                    "volumeNumber": volume_number,
                    "format": "Word",
                    "compilationNumber": "164",
                    "registerId": "C2026C00206",
                    "extension": ".docx",
                    "pageCount": None,
                    "sizeInBytes": 483340,
                    "isAuthorised": False,
                    "contents": contents,
                }
            )
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={"value": documents},
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        documents = client.list_documents("C2026C00206")

    assert [(document.volume_number, document.contents) for document in documents] == [
        (1, "s 1-53ZZC"),
        (4, "sch 1-Endnotes"),
    ]


def test_get_title_rejects_missing_required_identifier() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "name": "Privacy Act 1988",
                "makingDate": "1988-12-14T00:00:00",
                "collection": "Act",
                "isPrincipal": True,
                "isInForce": True,
                "status": "InForce",
                "hasCommencedUnincorporatedAmendments": False,
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="failed validation"):
            client.get_title("C2004A03712")


def test_get_title_rejects_response_identifier_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "id": "C2004A00109",
                "name": "Competition and Consumer Act 2010",
                "makingDate": "1974-08-24T00:00:00",
                "collection": "Act",
                "isPrincipal": True,
                "isInForce": True,
                "status": "InForce",
                "hasCommencedUnincorporatedAmendments": True,
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="identifier did not match"):
            client.get_title("C2004A03712")


def test_get_title_rejects_incompatible_required_field_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "id": 123,
                "name": "Privacy Act 1988",
                "makingDate": "1988-12-14T00:00:00",
                "collection": "Act",
                "isPrincipal": True,
                "isInForce": True,
                "status": "InForce",
                "hasCommencedUnincorporatedAmendments": False,
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="failed validation"):
            client.get_title("C2004A03712")


def test_get_title_rejects_string_for_strict_boolean_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "id": "C2004A03712",
                "name": "Privacy Act 1988",
                "makingDate": "1988-12-14T00:00:00",
                "collection": "Act",
                "isPrincipal": "true",
                "isInForce": True,
                "status": "InForce",
                "hasCommencedUnincorporatedAmendments": False,
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="failed validation"):
            client.get_title("C2004A03712")


@pytest.mark.parametrize(
    "making_date",
    ["1988-13-14T00:00:00", "1988-12-14T00:00:00+10:60"],
    ids=("invalid-month", "invalid-offset-minutes"),
)
def test_get_title_rejects_malformed_critical_timestamp(making_date: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "id": "C2004A03712",
                "name": "Privacy Act 1988",
                "makingDate": making_date,
                "collection": "Act",
                "isPrincipal": True,
                "isInForce": True,
                "status": "InForce",
                "hasCommencedUnincorporatedAmendments": False,
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="failed validation"):
            client.get_title("C2004A03712")


def test_get_title_tolerates_additive_unknown_upstream_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            json={
                "id": "C2004A03712",
                "name": "Privacy Act 1988",
                "makingDate": "1988-12-14T00:00:00",
                "collection": "Act",
                "isPrincipal": True,
                "isInForce": True,
                "status": "InForce",
                "hasCommencedUnincorporatedAmendments": False,
                "newUpstreamField": {"shape": "not-yet-modelled"},
            },
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        title = client.get_title("C2004A03712")

    assert title.title_id == "C2004A03712"


def test_get_title_rejects_non_success_status_without_exposing_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            headers={"Content-Type": "text/plain"},
            content=b"sensitive upstream diagnostic",
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="HTTP 503") as caught:
            client.get_title("C2004A03712")

    assert caught.value.__cause__ is None
    assert "Federal Register returned HTTP 503" == str(caught.value)
    assert "sensitive upstream diagnostic" not in str(caught.value)


def test_get_title_rejects_unexpected_content_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=b"<html></html>",
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="content type"):
            client.get_title("C2004A03712")


def test_get_title_rejects_malformed_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=b'{"id":',
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="malformed JSON"):
            client.get_title("C2004A03712")


@pytest.mark.parametrize(
    "body",
    [b"[]", b'"invalid-root"'],
    ids=("array", "string"),
)
def test_get_title_rejects_non_object_json_root(body: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=body,
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="root was not an object"):
            client.get_title("C2004A03712")


def test_get_title_accepts_metadata_response_at_exact_size_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=_title_response_body(1_048_576),
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        title = client.get_title("C2004A03712")

    assert title.title_id == "C2004A03712"


def test_get_title_rejects_metadata_response_one_byte_over_size_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=_title_response_body(1_048_577),
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="size limit"):
            client.get_title("C2004A03712")


def test_get_title_rejects_declared_oversize_before_consuming_stream() -> None:
    stream = RecordingByteStream(_title_response_body(512))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "Content-Type": "application/json",
                "Content-Length": "1048577",
            },
            stream=stream,
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="size limit"):
            client.get_title("C2004A03712")

    assert stream.chunks_yielded == 0


@pytest.mark.parametrize(
    "content_length",
    ["not-a-number", "+1", "1_0", " 1"],
    ids=("non-numeric", "leading-plus", "underscore", "leading-whitespace"),
)
def test_get_title_rejects_invalid_content_length_before_consuming_stream(
    content_length: str,
) -> None:
    stream = RecordingByteStream(_title_response_body(512))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "Content-Type": "application/json",
                "Content-Length": content_length,
            },
            stream=stream,
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="content length"):
            client.get_title("C2004A03712")

    assert stream.chunks_yielded == 0


def test_get_title_rejects_stream_that_crosses_size_limit() -> None:
    stream = RecordingByteStream(
        _title_response_body(1_048_570),
        b" " * 7,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            stream=stream,
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterResponseError, match="size limit"):
            client.get_title("C2004A03712")

    assert stream.chunks_yielded == 2


def test_get_title_rejects_redirect_to_non_approved_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"Location": "https://unapproved.example/collect"},
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterRedirectError, match="non-approved redirect destination"):
            client.get_title("C2004A03712")


def test_get_title_classifies_approved_host_redirect_before_refusing_it() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"Location": "https://api.prod.legislation.gov.au/v1/titles('C2004A03712')"},
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterRedirectError, match="approved-host redirects"):
            client.get_title("C2004A03712")


@pytest.mark.parametrize(
    ("location", "expected_message"),
    [
        ("/v1/titles('C2004A03712')", "approved-host redirects"),
        ("http://api.prod.legislation.gov.au/v1/titles", "non-approved redirect"),
        ("https://api.prod.legislation.gov.au.evil.com/v1/titles", "non-approved redirect"),
        ("https://api.prod.legislation.gov.au:444/v1/titles", "non-approved redirect"),
    ],
    ids=("relative-approved-host", "https-downgrade", "hostname-suffix", "non-443-port"),
)
def test_get_title_refuses_redirect_without_second_request_or_body_exposure(
    location: str,
    expected_message: str,
) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            302,
            headers={"Location": location},
            content=b"sensitive redirect body",
        )

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FederalRegisterRedirectError, match=expected_message) as caught:
            client.get_title("C2004A03712")

    assert request_count == 1
    assert "sensitive redirect body" not in str(caught.value)


@pytest.mark.parametrize(
    "identifier",
    [
        "C2004A0371'",
        "C2004A03%27",
        "C2004A0371 ",
        "C2004A0371/",
        "C2004A0371?",
        "C2004A0371\n",
    ],
    ids=("quote", "encoded-quote", "whitespace", "slash", "query", "control"),
)
def test_client_rejects_identifier_injection_before_transport(identifier: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500)

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            FederalRegisterRequestError,
            match="invalid Federal Register identifier",
        ):
            client.get_title(identifier)

    assert request_count == 0


def test_client_rejects_malformed_required_ids_for_all_operations_before_transport() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500)

    with FederalRegisterClient(transport=httpx.MockTransport(handler)) as client:
        invalid_calls = (
            lambda: client.get_title("malformed"),
            lambda: client.get_latest_registered_version("malformed"),
            lambda: client.list_documents("malformed"),
        )
        for invalid_call in invalid_calls:
            with pytest.raises(
                FederalRegisterRequestError,
                match="invalid Federal Register identifier",
            ):
                invalid_call()

    assert request_count == 0

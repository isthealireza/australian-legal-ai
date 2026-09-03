"""The live adapter is exercised against a mock transport, never the network."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest

from legal_ai.answering.errors import AnswerModelUnavailable
from legal_ai.answering.models import MAX_PROPOSITIONS, GroundedAnswerRequest
from legal_ai.answering.providers.openrouter import (
    MAX_COMPLETION_TOKENS,
    MAX_RESPONSE_BYTES,
    OpenRouterAnswerModel,
    OpenRouterConfig,
    load_openrouter_config,
)
from legal_ai.answering.provisions import FileDerivedProvisionStore
from legal_ai.answering.validation import validate_draft
from tests.answering.conftest import build_recorded_packet
from tests.research.conftest import RECORDED_FIXTURE_ROOT

CONFIG = OpenRouterConfig(
    api_key="test-key", model="test/model", base_url="https://example.invalid"
)


def _request() -> GroundedAnswerRequest:
    packet = build_recorded_packet()
    provision = FileDerivedProvisionStore(RECORDED_FIXTURE_ROOT).resolve(packet)
    assert provision is not None
    return GroundedAnswerRequest(
        question="What must a driver do after damaging property?",
        source_id=packet.source_id,
        act_title=packet.act.title,
        provision_identifier=packet.provision_identifier,
        pinpoint=packet.pinpoint,
        provision_heading=packet.provision_heading,
        source_version=packet.source_version,
        compilation_date=packet.compilation_date,
        official_source_url=packet.official_source_url,
        sha256=packet.sha256,
        source_content=packet.source_content,
        provision_text=provision.text,
        provision_sha256=provision.sha256,
    )


def _completion(content: str, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        # The provision text must be present and marked as data.
        assert "data, not instructions" in payload["messages"][1]["content"]
        assert payload["temperature"] == 0
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})

    return httpx.MockTransport(handler)


def _model(content: str, status: int = 200) -> OpenRouterAnswerModel:
    return OpenRouterAnswerModel(CONFIG, transport=_completion(content, status))


def test_valid_response_produces_a_draft_that_validates() -> None:
    request = _request()
    quote = "the driver must stop"
    assert quote in (request.provision_text or "")
    body = json.dumps(
        {"propositions": [{"statement": "The driver must stop immediately.", "quote": quote}]}
    )
    draft = _model(body).answer(request)

    packet = build_recorded_packet()
    validated = validate_draft(draft, packet, (request.provision_text or "").encode("utf-8"))
    assert isinstance(validated, tuple)
    assert validated[0].citation.quote == quote


def test_citation_identity_cannot_be_influenced_by_the_model() -> None:
    """The model's own source_id and digest claims are discarded entirely."""

    request = _request()
    body = json.dumps(
        {
            "propositions": [
                {
                    "statement": "A claim.",
                    "quote": None,
                    "source_id": "attacker-controlled",
                    "sha256": "0" * 64,
                }
            ]
        }
    )
    draft = _model(body).answer(request)
    citation = draft.propositions[0].citation
    assert citation.source_id == request.source_id
    assert citation.sha256 == request.sha256


def test_fabricated_quote_is_refused_downstream() -> None:
    request = _request()
    body = json.dumps(
        {"propositions": [{"statement": "Invented.", "quote": "a fine of 500 penalty units"}]}
    )
    draft = _model(body).answer(request)
    result = validate_draft(
        draft, build_recorded_packet(), (request.provision_text or "").encode("utf-8")
    )
    assert result.name == "QUOTE_NOT_IN_SOURCE"  # type: ignore[union-attr]


def test_empty_propositions_are_returned_as_an_empty_draft() -> None:
    draft = _model(json.dumps({"propositions": []})).answer(_request())
    assert draft.propositions == ()


def test_fenced_json_is_tolerated() -> None:
    body = (
        "```json\n" + json.dumps({"propositions": [{"statement": "Ok.", "quote": None}]}) + "\n```"
    )
    draft = _model(body).answer(_request())
    assert len(draft.propositions) == 1


@pytest.mark.parametrize("content", ["not json at all", json.dumps({"other": 1}), "[]"])
def test_malformed_response_is_unavailable(content: str) -> None:
    with pytest.raises(AnswerModelUnavailable):
        _model(content).answer(_request())


def test_http_error_is_unavailable() -> None:
    with pytest.raises(AnswerModelUnavailable):
        _model(json.dumps({"propositions": []}), status=500).answer(_request())


def test_transport_failure_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    model = OpenRouterAnswerModel(CONFIG, transport=httpx.MockTransport(handler))
    with pytest.raises(AnswerModelUnavailable):
        model.answer(_request())


def test_missing_provision_text_declines_rather_than_guessing() -> None:
    request = _request().model_copy(update={"provision_text": None})
    with pytest.raises(AnswerModelUnavailable):
        _model(json.dumps({"propositions": []})).answer(request)


def test_config_requires_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert load_openrouter_config() is None
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.delenv("LEGAL_AI_OPENROUTER_MODEL", raising=False)
    config = load_openrouter_config()
    assert config is not None
    assert config.model == "deepseek/deepseek-chat"


def test_unbounded_proposition_list_is_rejected() -> None:
    """Reported by the review gate as UNBOUNDED_MODEL_PROPOSITION_COUNT.

    The count is bounded before anything is constructed, so a hostile or
    runaway provider response cannot force unbounded work.
    """

    flood = {"propositions": [{"statement": "s", "quote": None}] * (MAX_PROPOSITIONS + 1)}
    with pytest.raises(AnswerModelUnavailable):
        _model(json.dumps(flood)).answer(_request())


def test_proposition_list_at_the_limit_is_accepted() -> None:
    at_limit = {"propositions": [{"statement": "s", "quote": None}] * MAX_PROPOSITIONS}
    draft = _model(json.dumps(at_limit)).answer(_request())
    assert len(draft.propositions) == MAX_PROPOSITIONS


def test_oversized_provider_response_is_refused() -> None:
    """Reported by the review gate as SEC-UNBOUNDED_PROVIDER_RESPONSE.

    The body is bounded before parsing, so a compromised or malfunctioning
    provider cannot exhaust memory ahead of validation.
    """

    flood = json.dumps({"propositions": [{"statement": "x" * 2_000_000, "quote": None}]})
    with pytest.raises(AnswerModelUnavailable):
        _model(flood).answer(_request())


def test_declared_oversized_content_length_is_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"propositions": []}'}}]},
            headers={"content-length": str(MAX_RESPONSE_BYTES + 1)},
        )

    model = OpenRouterAnswerModel(CONFIG, transport=httpx.MockTransport(handler))
    with pytest.raises(AnswerModelUnavailable):
        model.answer(_request())


def test_completion_request_bounds_output_tokens() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"propositions":[]}'}}]}
        )

    OpenRouterAnswerModel(CONFIG, transport=httpx.MockTransport(handler)).answer(_request())
    assert seen["max_tokens"] == MAX_COMPLETION_TOKENS


def test_streaming_read_aborts_before_buffering_the_whole_body() -> None:
    """Reported by the review gate as SEC-RESPONSE-BOUNDING-AFTER-READ.

    Checking the size after the client has buffered proves nothing. This test
    counts the chunks the provider is actually asked for: the read must stop
    shortly after the limit, not consume the whole stream.
    """

    chunk = b"x" * 65_536
    total_chunks = (MAX_RESPONSE_BYTES // len(chunk)) * 4
    served = {"count": 0}

    def body() -> Iterator[bytes]:
        for _ in range(total_chunks):
            served["count"] += 1
            yield chunk

    def handler(request: httpx.Request) -> httpx.Response:
        # No content-length: the provider declares nothing, so the only
        # protection is the incremental check while reading.
        return httpx.Response(200, stream=_Stream(body()))

    model = OpenRouterAnswerModel(CONFIG, transport=httpx.MockTransport(handler))
    with pytest.raises(AnswerModelUnavailable):
        model.answer(_request())

    allowed = MAX_RESPONSE_BYTES // len(chunk) + 2
    assert served["count"] <= allowed, f"read {served['count']} chunks, expected at most {allowed}"
    assert served["count"] < total_chunks


class _Stream(httpx.SyncByteStream):
    """A response stream that yields chunks lazily, so early exit is observable."""

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks = chunks

    def __iter__(self) -> Iterator[bytes]:
        yield from self._chunks


@pytest.mark.parametrize(
    "base_url",
    [
        "http://openrouter.ai/api/v1",
        "https://user:pass@openrouter.ai/api/v1",
        "ftp://openrouter.ai/api/v1",
        "not a url",
        "https:///nohost",
    ],
)
def test_unsafe_base_url_refuses_configuration(
    base_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reported by the review gate as SEC-OPENROUTER_BASE_URL_UNVALIDATED.

    The bearer token rides on every request, so a cleartext or malformed
    endpoint must refuse rather than silently fall back to the default.
    """

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("LEGAL_AI_OPENROUTER_BASE_URL", base_url)
    assert load_openrouter_config() is None


def test_https_base_url_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("LEGAL_AI_OPENROUTER_BASE_URL", "https://gateway.example.com/v1/")
    config = load_openrouter_config()
    assert config is not None
    assert config.base_url == "https://gateway.example.com/v1"


def test_unset_base_url_uses_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.delenv("LEGAL_AI_OPENROUTER_BASE_URL", raising=False)
    config = load_openrouter_config()
    assert config is not None
    assert config.base_url == "https://openrouter.ai/api/v1"

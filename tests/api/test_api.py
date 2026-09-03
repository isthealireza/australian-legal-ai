"""HTTP contract for the read-only research API."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal_ai.answering.verification import AlwaysSupportedVerifier
from legal_ai.api.main import create_app
from legal_ai.api.settings import DISCLAIMER, AnswerModelChoice, ApiSettings
from tests.research.conftest import RECORDED_ACT_TITLE, RECORDED_FIXTURE_ROOT

ANSWERABLE = {
    "question": "What must a driver do after damaging property?",
    "jurisdiction": "WA",
    "act_title": RECORDED_ACT_TITLE,
    "provision_identifier": "s 55",
    "pinpoint": "section 55",
}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = ApiSettings(
        corpus_root=RECORDED_FIXTURE_ROOT,
        audit_log_path=tmp_path / "research.jsonl",
        provision_root=RECORDED_FIXTURE_ROOT,
    )
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client


@pytest.fixture
def unconfigured_client() -> Iterator[TestClient]:
    settings = ApiSettings(corpus_root=None, audit_log_path=None)
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client


def test_health_reports_a_configured_corpus(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["corpus_configured"] is True
    assert body["answer_model"] == "mock"
    assert body["disclaimer"] == DISCLAIMER


def test_health_reports_an_unconfigured_corpus(unconfigured_client: TestClient) -> None:
    body = unconfigured_client.get("/api/health").json()
    assert body["corpus_configured"] is False


def test_answerable_question_returns_a_cited_answer(client: TestClient) -> None:
    response = client.post("/api/research", json=ANSWERABLE)
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "ANSWERED"
    assert body["disclaimer"] == DISCLAIMER

    citation = body["propositions"][0]["citation"]
    assert citation["act_title"] == RECORDED_ACT_TITLE
    assert citation["pinpoint"] == "section 55"
    assert citation["source_version"] == "14-t0-00"
    assert len(citation["sha256"]) == 64
    assert citation["official_source_url"].startswith("https://www.legislation.wa.gov.au/")


def test_out_of_corpus_question_is_refused_not_answered(client: TestClient) -> None:
    response = client.post("/api/research", json={**ANSWERABLE, "act_title": "Fictional Act 2099"})
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "REFUSED"
    assert body["code"] == "RESEARCH_REFUSED"
    assert "propositions" not in body


def test_wrong_jurisdiction_is_refused(client: TestClient) -> None:
    body = client.post("/api/research", json={**ANSWERABLE, "jurisdiction": "NSW"}).json()
    assert body["outcome"] == "REFUSED"


def test_unknown_pinpoint_is_refused(client: TestClient) -> None:
    body = client.post("/api/research", json={**ANSWERABLE, "pinpoint": "section 999"}).json()
    assert body["outcome"] == "REFUSED"


def test_unconfigured_corpus_reports_unavailable(unconfigured_client: TestClient) -> None:
    response = unconfigured_client.post("/api/research", json=ANSWERABLE)
    assert response.status_code == 503
    assert response.json()["code"] == "CORPUS_UNAVAILABLE"


def test_blank_field_is_refused_not_guessed(client: TestClient) -> None:
    body = client.post("/api/research", json={**ANSWERABLE, "act_title": "   "}).json()
    assert body["outcome"] == "REFUSED"


def test_unknown_field_is_rejected(client: TestClient) -> None:
    response = client.post("/api/research", json={**ANSWERABLE, "authority_level": "L3"})
    assert response.status_code == 422


def test_audit_trail_is_written_for_every_request(client: TestClient, tmp_path: Path) -> None:
    client.post("/api/research", json=ANSWERABLE)
    client.post("/api/research", json={**ANSWERABLE, "act_title": "Fictional Act 2099"})
    lines = (tmp_path / "research.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_interface_is_served_with_the_required_notices(client: TestClient) -> None:
    page = client.get("/").text
    assert "is not a lawyer" in page
    assert "currently indexed corpus" in page


def test_health_reports_entailment_state(client: TestClient) -> None:
    assert client.get("/api/health").json()["entailment_verified"] is False


def test_answer_carries_a_quote_from_the_verified_provision_text(client: TestClient) -> None:
    """With derived text wired, the answer quotes it and the quote validates."""

    body = client.post("/api/research", json=ANSWERABLE).json()
    quote = body["propositions"][0]["citation"]["quote"]
    assert quote is not None
    assert quote.startswith("55. Driver in incident")


def test_unknown_answer_model_falls_back_to_mock(tmp_path: Path) -> None:
    settings = ApiSettings(
        corpus_root=RECORDED_FIXTURE_ROOT,
        audit_log_path=tmp_path / "audit.jsonl",
        answer_model=AnswerModelChoice.MOCK,
    )
    with TestClient(create_app(settings=settings)) as test_client:
        assert test_client.get("/api/health").json()["answer_model"] == "mock"


def test_live_model_is_not_selected_without_an_explicit_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stray credential must never silently switch on a live provider."""

    monkeypatch.setenv("OPENROUTER_API_KEY", "should-not-be-used")
    settings = ApiSettings(
        corpus_root=RECORDED_FIXTURE_ROOT, audit_log_path=tmp_path / "audit.jsonl"
    )
    with TestClient(create_app(settings=settings)) as test_client:
        assert test_client.get("/api/health").json()["answer_model"] == "mock"


def test_requested_entailment_without_credentials_refuses_every_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A requested safety check that cannot be built must stop the service.

    Reported by the DeepSeek review gate as ENTAILMENT_SILENT_SKIP (high).
    """

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    settings = ApiSettings(
        corpus_root=RECORDED_FIXTURE_ROOT,
        audit_log_path=tmp_path / "audit.jsonl",
        provision_root=RECORDED_FIXTURE_ROOT,
        verify_entailment=True,
    )
    with TestClient(create_app(settings=settings)) as test_client:
        health = test_client.get("/api/health").json()
        assert health["corpus_configured"] is False
        assert health["entailment_verified"] is False

        response = test_client.post("/api/research", json=ANSWERABLE)
        assert response.status_code == 503
        body = response.json()
        assert body["outcome"] == "REFUSED"
        assert body["code"] == "VERIFIER_NOT_CONFIGURED"
        assert "propositions" not in body


def test_health_reports_a_configured_verifier(tmp_path: Path) -> None:
    settings = ApiSettings(
        corpus_root=RECORDED_FIXTURE_ROOT,
        audit_log_path=tmp_path / "audit.jsonl",
        provision_root=RECORDED_FIXTURE_ROOT,
        verify_entailment=True,
    )
    app = create_app(settings=settings, verifier=AlwaysSupportedVerifier())
    with TestClient(app) as test_client:
        health = test_client.get("/api/health").json()
        assert health["entailment_verified"] is True
        assert health["corpus_configured"] is True
        assert test_client.post("/api/research", json=ANSWERABLE).json()["outcome"] == "ANSWERED"


@pytest.mark.parametrize(
    "overrides",
    [
        {"question": "x" * 5000},
        {"question": ""},
        {"act_title": "y" * 5000},
        {"pinpoint": "z" * 300},
    ],
)
def test_oversized_or_empty_fields_are_rejected_at_the_boundary(
    client: TestClient, overrides: dict[str, str]
) -> None:
    """Reported by the review gate as UNHANDLED_OVERSIZED_QUESTION_VALIDATION_ERROR.

    An over-long field must be a 422 at the HTTP boundary, never an unhandled
    validation error raised from inside the pipeline.
    """

    response = client.post("/api/research", json={**ANSWERABLE, **overrides})
    assert response.status_code == 422


def test_maximum_length_question_is_still_served(client: TestClient) -> None:
    response = client.post("/api/research", json={**ANSWERABLE, "question": "q" * 4096})
    assert response.status_code == 200
    assert response.json()["outcome"] == "ANSWERED"


def test_live_model_without_entailment_refuses_every_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reported by the review gate as LIVE_PROVIDER_WITHOUT_ENTAILMENT.

    Levels 1 and 2 constrain the citation, not the statement. A mock cannot
    invent a statement; a live generative model can, so it may not answer
    without level 3.
    """

    monkeypatch.setenv("OPENROUTER_API_KEY", "present-but-verification-is-off")
    settings = ApiSettings(
        corpus_root=RECORDED_FIXTURE_ROOT,
        audit_log_path=tmp_path / "audit.jsonl",
        provision_root=RECORDED_FIXTURE_ROOT,
        answer_model=AnswerModelChoice.OPENROUTER,
        verify_entailment=False,
    )
    with TestClient(create_app(settings=settings)) as test_client:
        assert test_client.get("/api/health").json()["corpus_configured"] is False
        response = test_client.post("/api/research", json=ANSWERABLE)
        assert response.status_code == 503
        assert response.json()["code"] == "ENTAILMENT_REQUIRED_FOR_LIVE_MODEL"


def test_mock_model_without_entailment_is_permitted(client: TestClient) -> None:
    """The requirement is specific to a live provider, not to answering at all."""

    assert client.get("/api/health").json()["answer_model"] == "mock"
    assert client.post("/api/research", json=ANSWERABLE).json()["outcome"] == "ANSWERED"


def test_unwritable_audit_log_stops_the_service_without_crashing(tmp_path: Path) -> None:
    """Reported by the review gate as OPS-AUDIT_SINK_STARTUP_FAILURE.

    An audit trail that cannot be written must stop the service, not crash the
    process and not answer without auditing.
    """

    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    settings = ApiSettings(
        corpus_root=RECORDED_FIXTURE_ROOT,
        audit_log_path=blocker / "nested" / "research.jsonl",
        provision_root=RECORDED_FIXTURE_ROOT,
    )

    app = create_app(settings=settings)
    with TestClient(app) as test_client:
        assert test_client.get("/api/health").json()["corpus_configured"] is False
        response = test_client.post("/api/research", json=ANSWERABLE)
        assert response.status_code == 503
        assert response.json()["code"] == "AUDIT_SINK_NOT_WRITABLE"

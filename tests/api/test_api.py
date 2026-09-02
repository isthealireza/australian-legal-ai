"""HTTP contract for the read-only research API."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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

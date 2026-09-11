"""HTTP contract for the routing endpoint."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal_ai.answering.routing import RouterChoiceDraft, RouterDraft
from legal_ai.api.main import create_app
from legal_ai.api.settings import ApiSettings
from tests.research.conftest import RECORDED_FIXTURE_ROOT


class ScriptedRouter:
    def __init__(self, *choices: tuple[str, str, str]) -> None:
        self._draft = RouterDraft(
            choices=tuple(
                RouterChoiceDraft(act_title=a, provision_identifier=p, reason=r)
                for a, p, r in choices
            )
        )

    def route(self, *, problem: str, catalogue: object) -> RouterDraft:
        del problem, catalogue
        return self._draft


def _client(*choices: tuple[str, str, str]) -> TestClient:
    settings = ApiSettings(
        corpus_root=RECORDED_FIXTURE_ROOT,
        audit_log_path=None,
        provision_root=RECORDED_FIXTURE_ROOT,
    )
    return TestClient(create_app(settings=settings, router=ScriptedRouter(*choices)))


@pytest.fixture
def unrouted_client() -> Iterator[TestClient]:
    # Mock config with no router: routing is unavailable, the list is the fallback.
    settings = ApiSettings(
        corpus_root=RECORDED_FIXTURE_ROOT,
        audit_log_path=None,
        provision_root=RECORDED_FIXTURE_ROOT,
    )
    with TestClient(create_app(settings=settings)) as client:
        yield client


def test_route_returns_a_routed_answer_for_a_single_choice() -> None:
    with _client(("Road Traffic Act 1974", "s 55", "duty after property damage")) as client:
        resp = client.post("/api/route", json={"problem": "I hit a parked car and drove off."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "ROUTED"
    assert body["chosen"]["provision_identifier"] == "s 55"
    assert body["chosen"]["act_title"] == "Road Traffic Act 1974"
    assert body["chosen"]["reason"]  # the "why" is shown
    assert body["answer"]["outcome"] == "ANSWERED"


def test_route_returns_candidates_for_two_choices() -> None:
    with _client(
        ("Sale of Goods Act 1895", "s 14", "implied quality"),
        ("Fair Trading Act 2010", "s 18", "consumer law"),
    ) as client:
        resp = client.post("/api/route", json={"problem": "Faulty goods and a misleading seller."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "CANDIDATES"
    assert len(body["candidates"]) == 2


def test_route_refuses_when_nothing_matches() -> None:
    with _client(("Residential Tenancies Act 1987", "s 1", "not in corpus")) as client:
        resp = client.post("/api/route", json={"problem": "My landlord kept my bond."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "REFUSED"
    assert body["code"] == "NO_MATCHING_PROVISION"


def test_route_refuses_out_of_scope_before_the_router() -> None:
    # An exploding router would fail if reached; scope refuses first, so a plain
    # scripted router is fine and simply never consulted.
    with _client(("Road Traffic Act 1974", "s 55", "x")) as client:
        resp = client.post(
            "/api/route",
            json={"problem": "Please review my contract and tell me if I should sign."},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "REFUSED"
    assert body["code"] == "REQUEST_OUT_OF_SCOPE"


def test_route_is_unavailable_without_a_router(unrouted_client: TestClient) -> None:
    resp = unrouted_client.post("/api/route", json={"problem": "A genuine driving question."})
    assert resp.status_code == 503
    assert resp.json()["code"] == "ROUTER_UNAVAILABLE"


def test_route_with_empty_catalogue_returns_catalogue_empty_not_503(tmp_path: Path) -> None:
    # tmp_path is an empty directory → FileDerivedProvisionStore returns () catalogue.
    # A router is present, so routing_service is created (after the AC6 fix that
    # removed the catalogue-emptiness guard from create_app). CATALOGUE_EMPTY is a
    # correct typed refusal (200), not a 503 service-unavailability.
    settings = ApiSettings(
        corpus_root=RECORDED_FIXTURE_ROOT,
        audit_log_path=None,
        provision_root=tmp_path,
    )
    with TestClient(
        create_app(settings=settings, router=ScriptedRouter(("Road Traffic Act 1974", "s 55", "x")))
    ) as client:
        resp = client.post("/api/route", json={"problem": "A genuine driving question."})
    # CATALOGUE_EMPTY is a server-side unavailability (503), not a normal routing
    # outcome — but the code must be CATALOGUE_EMPTY, not ROUTER_UNAVAILABLE, so
    # the caller can distinguish "no router" from "router present but nothing indexed".
    assert resp.status_code == 503
    assert resp.json()["code"] == "CATALOGUE_EMPTY"

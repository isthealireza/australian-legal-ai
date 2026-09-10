"""The routing endpoint: a described problem in, a provision decision out.

Routing sits in front of the research endpoint. It refuses an out-of-scope
request before any model call, selects only from the indexed catalogue,
validates that choice deterministically, and then either runs the unchanged
research pipeline for a single provision, offers a short candidate list, or
refuses. It never invents an Act or a section.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from ...answering.routing import (
    ProvisionRoutingService,
    RouteCandidates,
    RoutedAnswer,
    RouteRefusalCode,
    RouteRefused,
)
from ..schemas import (
    RouteCandidatesBody,
    RoutedAnswerBody,
    RouteRefusalBody,
    RouteRequestBody,
    render_route_candidates,
    render_route_refusal,
    render_routed_answer,
)
from ..settings import DISCLAIMER

router = APIRouter(tags=["routing"])

#: A router that could not decide, or a catalogue that is not there, is a
#: server-side unavailability rather than a normal routing outcome.
_UNAVAILABLE = frozenset(
    {
        RouteRefusalCode.ROUTER_UNAVAILABLE,
        RouteRefusalCode.CATALOGUE_EMPTY,
    }
)


@router.post("/api/route", response_model=None)
def route(
    body: RouteRequestBody, request: Request, response: Response
) -> RoutedAnswerBody | RouteCandidatesBody | RouteRefusalBody:
    """Route one described problem to a provision, a candidate list, or a refusal."""

    service = request.app.state.routing_service
    if not isinstance(service, ProvisionRoutingService):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return RouteRefusalBody(disclaimer=DISCLAIMER, code=RouteRefusalCode.ROUTER_UNAVAILABLE)

    outcome = service.route(body.problem)
    if isinstance(outcome, RoutedAnswer):
        return render_routed_answer(outcome, DISCLAIMER)
    if isinstance(outcome, RouteCandidates):
        return render_route_candidates(outcome, DISCLAIMER)
    if isinstance(outcome, RouteRefused):
        if outcome.code in _UNAVAILABLE:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return render_route_refusal(outcome, DISCLAIMER)
    # Unreachable by the outcome contract; refuse rather than fall through.
    return RouteRefusalBody(  # pragma: no cover - exhaustive guard
        disclaimer=DISCLAIMER, code=RouteRefusalCode.ROUTER_UNAVAILABLE
    )

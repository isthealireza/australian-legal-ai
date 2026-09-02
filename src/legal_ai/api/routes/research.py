"""The single read-only research endpoint.

The route performs no legal reasoning of its own. It converts a request body
into a `ResearchQuery`, hands it to the grounded pipeline, and renders whatever
that pipeline returns. A refusal is rendered as a refusal, never as an empty
answer or a soft partial result.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from pydantic import ValidationError

from ...answering.models import AnswerRefused, GroundedAnswer
from ...answering.service import AnswerQuestion, GroundedAnswerService
from ...answering.types import AnswerRefusalCode
from ...research.models import ResearchQuery
from ..schemas import AnswerBody, RefusalBody, ResearchRequestBody, render_answer
from ..settings import DISCLAIMER

router = APIRouter(tags=["research"])

#: A refusal is a successful, correct outcome of the contract, not a client
#: error, so it is returned as 200 with an explicit REFUSED outcome. Only an
#: unconfigured corpus is reported as a server-side unavailability.
_UNAVAILABLE = frozenset({AnswerRefusalCode.CORPUS_UNAVAILABLE})


@router.post("/api/research", response_model=None)
def research(
    body: ResearchRequestBody, request: Request, response: Response
) -> AnswerBody | RefusalBody:
    """Answer one question strictly from the indexed corpus, or refuse."""

    service = request.app.state.answer_service
    if not isinstance(service, GroundedAnswerService):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return RefusalBody(disclaimer=DISCLAIMER, code=AnswerRefusalCode.CORPUS_UNAVAILABLE)

    try:
        query = ResearchQuery(
            jurisdiction=body.jurisdiction,
            act_title=body.act_title,
            provision_identifier=body.provision_identifier,
            pinpoint=body.pinpoint,
        )
        question = AnswerQuestion(question=body.question, query=query)
    except ValidationError:
        # A malformed query cannot be answered and is never guessed at.
        return RefusalBody(disclaimer=DISCLAIMER, code=AnswerRefusalCode.RESEARCH_REFUSED)

    result = service.answer(question)
    if isinstance(result, GroundedAnswer):
        return render_answer(result, DISCLAIMER)
    if isinstance(result, AnswerRefused):
        if result.code in _UNAVAILABLE:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return RefusalBody(disclaimer=DISCLAIMER, code=result.code)
    # Unreachable by the result contract; refuse rather than fall through.
    return RefusalBody(  # pragma: no cover - exhaustive guard
        disclaimer=DISCLAIMER, code=AnswerRefusalCode.RESEARCH_TERMINATED
    )

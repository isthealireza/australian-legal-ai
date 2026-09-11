"""Liveness and configuration reporting."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import HealthBody
from ..settings import DISCLAIMER

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health(request: Request) -> HealthBody:
    """Report liveness, whether a corpus is configured, and the active model."""

    return HealthBody(
        status="ok",
        corpus_configured=bool(request.app.state.corpus_configured),
        answer_model=str(request.app.state.answer_model_name),
        entailment_verified=bool(request.app.state.entailment_verified),
        disclaimer=DISCLAIMER,
    )

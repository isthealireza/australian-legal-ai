"""FastAPI application factory for the read-only WA research API.

Authority level L0. The service performs no live retrieval of legal sources, no
persistence, no database access, and no external action. It exposes two
endpoints over the merged Phase 4 research module plus the Phase 5 grounded
answering pipeline, and serves a static interface carrying the required notices.

The application never answers from model memory: every response is either a
fully validated, fully cited answer or an explicit typed refusal.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..answering.audit_sinks import JsonlResearchAuditSink, LoggingResearchAuditSink
from ..answering.mock import MockAnswerModel
from ..answering.protocol import LegalAnswerModel
from ..answering.providers import OpenRouterAnswerModel, load_openrouter_config
from ..answering.provisions import (
    DerivedProvisionStore,
    FileDerivedProvisionStore,
    NullDerivedProvisionStore,
)
from ..answering.service import GroundedAnswerService
from ..answering.verification import EntailmentVerifier, OpenRouterEntailmentVerifier
from ..research.audit import ResearchAuditSink
from ..research.corpus import RecordedWaCorpus
from ..research.errors import RecordedCorpusError
from ..research.service import WaResearchService
from .routes import health, research
from .settings import AnswerModelChoice, ApiSettings, load_settings

ENV_STATIC_DIR = "LEGAL_AI_STATIC_DIR"

TITLE = "Grounded WA Legislation Research Assistant"
SUMMARY = "Read-only, fail-closed research over an indexed corpus of official WA sources."


def _static_dir() -> Path | None:
    """Resolve the interface directory from the environment, or alongside the repo."""

    override = os.environ.get(ENV_STATIC_DIR, "").strip()
    if override:
        candidate = Path(override)
        return candidate if candidate.is_dir() else None
    bundled = Path(__file__).resolve().parents[3] / "static"
    return bundled if bundled.is_dir() else None


def _audit_sink(settings: ApiSettings) -> ResearchAuditSink:
    """Build the audit sink. A configured path is preferred over the logger."""

    if settings.audit_log_path is not None:
        return JsonlResearchAuditSink(settings.audit_log_path)
    return LoggingResearchAuditSink()


def _provision_store(settings: ApiSettings) -> DerivedProvisionStore:
    """Build the digest-chained provision store, or a store that resolves nothing."""

    root = settings.provision_root if settings.provision_root is not None else settings.corpus_root
    if root is None:
        return NullDerivedProvisionStore()
    return FileDerivedProvisionStore(root)


def _resolve_model(settings: ApiSettings) -> LegalAnswerModel:
    """Select the answer model. Falls back to the mock rather than failing open."""

    if settings.answer_model is AnswerModelChoice.OPENROUTER:
        config = load_openrouter_config()
        if config is not None:
            return OpenRouterAnswerModel(config)
    return MockAnswerModel()


def _resolve_verifier(settings: ApiSettings) -> EntailmentVerifier | None:
    """Build the level-3 verifier only when it is explicitly requested."""

    if not settings.verify_entailment:
        return None
    config = load_openrouter_config()
    if config is None:
        return None
    return OpenRouterEntailmentVerifier(config)


def _answer_service(
    settings: ApiSettings,
    model: LegalAnswerModel,
    verifier: EntailmentVerifier | None,
) -> GroundedAnswerService | None:
    """Wire the pipeline, or return None when no corpus is configured."""

    if settings.corpus_root is None:
        return None
    try:
        corpus = RecordedWaCorpus(settings.corpus_root)
    except RecordedCorpusError:
        # An unreadable corpus is reported as unavailable rather than crashing
        # the process or silently answering from nothing.
        return None
    return GroundedAnswerService(
        research=WaResearchService(corpus=corpus, audit_sink=_audit_sink(settings)),
        model=model,
        provisions=_provision_store(settings),
        verifier=verifier,
    )


def create_app(
    *,
    settings: ApiSettings | None = None,
    model: LegalAnswerModel | None = None,
    verifier: EntailmentVerifier | None = None,
) -> FastAPI:
    """Build the application. Every dependency is injectable for tests."""

    resolved = settings if settings is not None else load_settings()
    answer_model = model if model is not None else _resolve_model(resolved)
    entailment = verifier if verifier is not None else _resolve_verifier(resolved)

    app = FastAPI(title=TITLE, summary=SUMMARY, version="0.2.0")
    service = _answer_service(resolved, answer_model, entailment)
    app.state.answer_service = service
    app.state.corpus_configured = service is not None
    app.state.answer_model_name = getattr(answer_model, "name", type(answer_model).__name__)
    app.state.entailment_verified = entailment is not None

    app.include_router(health.router)
    app.include_router(research.router)

    static_dir = _static_dir()
    if static_dir is not None:
        index = static_dir / "index.html"
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/", include_in_schema=False)
        def interface() -> FileResponse:
            """Serve the single-page interface."""

            return FileResponse(index)

    return app

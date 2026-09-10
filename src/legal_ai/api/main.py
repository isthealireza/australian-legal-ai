"""FastAPI application factory for the read-only WA research API.

Authority level L0. The service performs no live retrieval of legal sources, no
persistence, no database access, and no external action. It exposes two
endpoints over the merged Phase 4 research module plus the Phase 5 grounded
answering pipeline, and serves a static interface carrying the required notices.

The application never answers from model memory: every response is either a
fully validated, fully cited answer or an explicit typed refusal.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..answering.audit_sinks import JsonlResearchAuditSink, LoggingResearchAuditSink
from ..answering.mock import MockAnswerModel
from ..answering.protocol import LegalAnswerModel
from ..answering.providers.chain import ChainedAnswerModel, NamedAnswerModel
from ..answering.providers.openrouter import ChatCompletionsAnswerModel
from ..answering.providers.registry import (
    MOCK,
    answer_chain_specs,
    answer_provider_name,
    build_config,
    verify_chain_specs,
)
from ..answering.providers.router import ChatCompletionsProvisionRouter
from ..answering.provisions import (
    DerivedProvisionStore,
    FileDerivedProvisionStore,
    NullDerivedProvisionStore,
)
from ..answering.routing import ProvisionRouter, ProvisionRoutingService
from ..answering.service import GroundedAnswerService
from ..answering.types import AnswerRefusalCode
from ..answering.verification import (
    ChainedEntailmentVerifier,
    ChatCompletionsEntailmentVerifier,
    EntailmentVerifier,
    NamedVerifier,
)
from ..research.audit import ResearchAuditSink
from ..research.corpus import RecordedWaCorpus
from ..research.errors import RecordedCorpusError, ResearchAuditSinkUnavailable
from ..research.service import WaResearchService
from .routes import corpus, health, research, route
from .settings import AnswerModelChoice, ApiSettings, load_settings

_LOGGER = logging.getLogger("legal_ai.api")

ENV_STATIC_DIR = "LEGAL_AI_STATIC_DIR"

TITLE = "Grounded WA Legislation Research Assistant"
SUMMARY = "Read-only, fail-closed research over an indexed corpus of official WA sources."


def _static_dir() -> Path | None:
    """Resolve the interface directory from the environment, or alongside the repo."""

    override = os.environ.get(ENV_STATIC_DIR, "").strip()
    if override:
        candidate = Path(override)
        # A symlinked interface directory is refused: what is served should be
        # what the operator can see at the configured path.
        if candidate.is_symlink() or not candidate.is_dir():
            return None
        return candidate
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
    """Build the answer chain from the environment, or fall back to the mock.

    A provider whose credential is absent is skipped, not guessed at. If the
    chain ends up empty the mock is used, which answers from packet identity
    alone and cannot invent anything.
    """

    del settings
    if answer_provider_name() == MOCK:
        return MockAnswerModel()

    members: list[NamedAnswerModel] = []
    for provider, model in answer_chain_specs():
        config = build_config(provider, model)
        if config is None:
            _LOGGER.warning("answer provider %s is not configured and will be skipped", provider)
            continue
        members.append(NamedAnswerModel(name=provider, model=ChatCompletionsAnswerModel(config)))

    if not members:
        _LOGGER.warning("no answer provider is configured; using the mock adapter")
        return MockAnswerModel()
    _LOGGER.info("answer chain: %s", ", ".join(member.name for member in members))
    return ChainedAnswerModel(members)


def _resolve_router(settings: ApiSettings) -> ProvisionRouter | None:
    """Build a model-backed router from the primary answer provider, if any.

    Routing needs a model to weigh known options. Without a live provider there
    is no router: the endpoint reports itself unavailable and the situation list
    remains the fallback, rather than a mock inventing a choice.
    """

    del settings
    if answer_provider_name() == MOCK:
        return None
    specs = answer_chain_specs()
    if not specs:
        return None
    provider, model = specs[0]
    config = build_config(provider, model)
    if config is None:
        return None
    return ChatCompletionsProvisionRouter(config)


def _resolve_verifier(settings: ApiSettings) -> EntailmentVerifier | None:
    """Build the level-3 verifier chain only when it is explicitly requested."""

    if not settings.verify_entailment:
        return None

    members: list[NamedVerifier] = []
    for provider, model in verify_chain_specs():
        config = build_config(provider, model)
        if config is None:
            continue
        members.append(
            NamedVerifier(name=provider, verifier=ChatCompletionsEntailmentVerifier(config))
        )

    if not members:
        return None
    _LOGGER.info("verifier chain: %s", ", ".join(member.name for member in members))
    return ChainedEntailmentVerifier(members)


def _configuration_error(
    settings: ApiSettings, verifier: EntailmentVerifier | None
) -> AnswerRefusalCode | None:
    """Return the refusal code for a configuration that cannot be honoured.

    Entailment verification that was asked for but cannot be built must stop
    the service, not quietly disappear. Silently answering without a requested
    safety check is worse than refusing, because the answer looks identical to
    one that passed the check.
    """

    if settings.verify_entailment and verifier is None:
        return AnswerRefusalCode.VERIFIER_NOT_CONFIGURED

    # Keyed on the resolved provider, not on one provider's name. Any live
    # generative provider is covered, so adding a fallback cannot become a way
    # around the rule.
    live = settings.answer_model is AnswerModelChoice.OPENROUTER or answer_provider_name() != MOCK
    if live and verifier is None:
        # Levels 1 and 2 prove a citation points at the retrieved provision and
        # that any quote is really in it. Neither constrains the *statement*. A
        # mock adapter cannot invent one; a live generative model can, so it may
        # not answer legal questions without level 3.
        return AnswerRefusalCode.ENTAILMENT_REQUIRED_FOR_LIVE_MODEL
    return None


def _answer_service(
    settings: ApiSettings,
    model: LegalAnswerModel,
    verifier: EntailmentVerifier | None,
) -> GroundedAnswerService | AnswerRefusalCode:
    """Wire the pipeline, or return the code explaining why it is unavailable."""

    if settings.corpus_root is None:
        return AnswerRefusalCode.CORPUS_UNAVAILABLE
    try:
        corpus = RecordedWaCorpus(settings.corpus_root)
    except RecordedCorpusError:
        # An unreadable corpus is reported as unavailable rather than crashing
        # the process or silently answering from nothing.
        return AnswerRefusalCode.CORPUS_UNAVAILABLE
    try:
        audit_sink = _audit_sink(settings)
    except ResearchAuditSinkUnavailable:
        # An audit trail that cannot be written is a stopped service, not a
        # crashed process and not a service that answers without auditing.
        return AnswerRefusalCode.AUDIT_SINK_NOT_WRITABLE
    return GroundedAnswerService(
        research=WaResearchService(corpus=corpus, audit_sink=audit_sink),
        model=model,
        provisions=_provision_store(settings),
        verifier=verifier,
    )


def create_app(
    *,
    settings: ApiSettings | None = None,
    model: LegalAnswerModel | None = None,
    verifier: EntailmentVerifier | None = None,
    router: ProvisionRouter | None = None,
) -> FastAPI:
    """Build the application. Every dependency is injectable for tests."""

    resolved = settings if settings is not None else load_settings()
    answer_model = model if model is not None else _resolve_model(resolved)
    entailment = verifier if verifier is not None else _resolve_verifier(resolved)
    provision_router = router if router is not None else _resolve_router(resolved)

    app = FastAPI(title=TITLE, summary=SUMMARY, version="0.2.0")
    config_error = _configuration_error(resolved, entailment)
    wired = config_error or _answer_service(resolved, answer_model, entailment)
    service = wired if isinstance(wired, GroundedAnswerService) else None
    app.state.answer_service = service
    app.state.unavailable_code = (
        AnswerRefusalCode.CORPUS_UNAVAILABLE if service is not None else wired
    )
    app.state.corpus_configured = service is not None
    providers = getattr(answer_model, "providers", None)
    app.state.answer_model_name = (
        "+".join(providers) if providers else getattr(answer_model, "name", "unknown")
    )
    app.state.entailment_verified = entailment is not None
    provisions = _provision_store(resolved)
    app.state.catalogue = (
        provisions.catalogue() if isinstance(provisions, FileDerivedProvisionStore) else ()
    )
    # Routing needs the answer service, a router, and a non-empty catalogue.
    # Missing any of these, the endpoint reports unavailable and the situation
    # list stays as the fallback.
    app.state.routing_service = (
        ProvisionRoutingService(
            router=provision_router,
            answer_service=service,
            catalogue=app.state.catalogue,
        )
        if service is not None and provision_router is not None and app.state.catalogue
        else None
    )

    app.include_router(corpus.router)
    app.include_router(health.router)
    app.include_router(research.router)
    app.include_router(route.router)

    static_dir = _static_dir()
    if static_dir is not None:
        index = static_dir / "index.html"
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/", include_in_schema=False)
        def interface() -> FileResponse:
            """Serve the single-page interface."""

            return FileResponse(index)

    return app

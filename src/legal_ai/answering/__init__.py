"""Phase 5 grounded answering: provider-neutral model contract and pipeline."""

from .errors import AnsweringError, AnswerModelUnavailable, AuditSinkUnavailable
from .mock import MockAnswerModel
from .models import (
    AnswerRefused,
    AnswerResult,
    Citation,
    DraftCitation,
    DraftProposition,
    GroundedAnswer,
    GroundedAnswerRequest,
    ModelDraft,
    Proposition,
)
from .protocol import LegalAnswerModel
from .providers import OpenRouterAnswerModel, OpenRouterConfig, load_openrouter_config
from .provisions import (
    DerivedProvision,
    DerivedProvisionStore,
    FileDerivedProvisionStore,
    NullDerivedProvisionStore,
)
from .service import AnswerQuestion, GroundedAnswerService
from .types import AnswerOutcome, AnswerRefusalCode
from .validation import validate_draft
from .verification import (
    EntailmentVerifier,
    OpenRouterEntailmentVerifier,
    VerifierUnavailable,
)

__all__ = [
    "AnswerModelUnavailable",
    "AnswerOutcome",
    "AnswerQuestion",
    "AnswerRefusalCode",
    "AnswerRefused",
    "AnswerResult",
    "AnsweringError",
    "AuditSinkUnavailable",
    "Citation",
    "DerivedProvision",
    "DerivedProvisionStore",
    "DraftCitation",
    "DraftProposition",
    "EntailmentVerifier",
    "FileDerivedProvisionStore",
    "GroundedAnswer",
    "GroundedAnswerRequest",
    "GroundedAnswerService",
    "LegalAnswerModel",
    "MockAnswerModel",
    "ModelDraft",
    "NullDerivedProvisionStore",
    "OpenRouterAnswerModel",
    "OpenRouterConfig",
    "OpenRouterEntailmentVerifier",
    "Proposition",
    "VerifierUnavailable",
    "load_openrouter_config",
    "validate_draft",
]

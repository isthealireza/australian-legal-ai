"""Environment-driven API settings.

Every path and credential is supplied by the environment. No absolute path and
no secret is embedded in code (ENGINEERING_WORKFLOW rules 7 and 8).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

ENV_CORPUS_ROOT = "LEGAL_AI_WA_CORPUS_ROOT"
ENV_PROVISION_ROOT = "LEGAL_AI_PROVISION_ROOT"
ENV_AUDIT_LOG = "LEGAL_AI_RESEARCH_AUDIT_LOG"
ENV_ANSWER_MODEL = "LEGAL_AI_ANSWER_MODEL"
ENV_VERIFY_ENTAILMENT = "LEGAL_AI_VERIFY_ENTAILMENT"

#: Shown on every response and permanently in the interface. MVP_ROADMAP
#: section 3 requires both notices to be present and non-dismissable.
DISCLAIMER = (
    "This prototype is not a lawyer and does not give legal advice. "
    "It answers only questions supported by its currently indexed corpus."
)


class AnswerModelChoice(StrEnum):
    """Which answer-model adapter to wire.

    `mock` is the default. Selecting a live provider is Phase 11 work and is
    gated behind the evaluation metrics in MVP_ROADMAP section 9, so it must be
    requested explicitly and is never inferred from a stray credential.
    """

    MOCK = "mock"
    OPENROUTER = "openrouter"


@dataclass(frozen=True, slots=True)
class ApiSettings:
    """Resolved runtime configuration for the read-only research API."""

    corpus_root: Path | None
    audit_log_path: Path | None
    provision_root: Path | None = None
    answer_model: AnswerModelChoice = AnswerModelChoice.MOCK
    verify_entailment: bool = False

    @property
    def corpus_configured(self) -> bool:
        """Whether a recorded corpus root has been supplied."""

        return self.corpus_root is not None


def _optional_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else None


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _answer_model() -> AnswerModelChoice:
    raw = os.environ.get(ENV_ANSWER_MODEL, "").strip().lower()
    if raw == AnswerModelChoice.OPENROUTER:
        return AnswerModelChoice.OPENROUTER
    # Anything unset or unrecognised falls back to the mock rather than
    # silently reaching for a live provider.
    return AnswerModelChoice.MOCK


def load_settings() -> ApiSettings:
    """Read settings from the process environment."""

    return ApiSettings(
        corpus_root=_optional_path(ENV_CORPUS_ROOT),
        audit_log_path=_optional_path(ENV_AUDIT_LOG),
        provision_root=_optional_path(ENV_PROVISION_ROOT),
        answer_model=_answer_model(),
        verify_entailment=_flag(ENV_VERIFY_ENTAILMENT),
    )

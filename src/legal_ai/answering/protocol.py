"""The provider-neutral answer-model contract (MVP_ROADMAP section 5).

An implementation is handed one `GroundedAnswerRequest` and returns one
`ModelDraft`. It is given no tools, no shell, no browser, no network, no
filesystem, and no persistent memory: the protocol has exactly one method and
that method takes exactly the evidence it is allowed to use.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import GroundedAnswerRequest, ModelDraft


@runtime_checkable
class LegalAnswerModel(Protocol):
    """Produce a structured draft from one evidence packet, or raise."""

    def answer(self, request: GroundedAnswerRequest) -> ModelDraft:
        """Return a structured draft, or raise `AnswerModelUnavailable`."""

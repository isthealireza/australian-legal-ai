"""Ordered provider fallback for answering and for entailment verification.

Resilience here means trying the next provider when one fails, never relaxing
what counts as an acceptable answer. A draft returned by a fallback goes
through exactly the same citation, quote, digest, and entailment checks as one
returned by the primary. Falling back changes who was asked, not what is
believed.

The budget matters as much as the order. Attempts share one wall-clock
allowance, so adding a fallback cannot push the total past the deadline the
interface is waiting on: a chain of three slow providers fails closed in the
same time a single slow provider would.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass

from ..errors import AnswerModelUnavailable
from ..models import GroundedAnswerRequest, ModelDraft
from ..protocol import LegalAnswerModel

_LOGGER = logging.getLogger("legal_ai.answering.providers")

#: Whole-phase allowance shared by every answer attempt, and the most any one
#: attempt may take. Two attempts at the cap still leave room for verification
#: inside the interface's 120-second abort.
ANSWER_PHASE_SECONDS = 70.0
ANSWER_ATTEMPT_SECONDS = 35.0


@dataclass(frozen=True, slots=True)
class NamedAnswerModel:
    """One provider in the chain, with the name used for logging and exclusion."""

    name: str
    model: LegalAnswerModel


@dataclass(frozen=True, slots=True)
class AnsweredBy:
    """A draft together with the provider that actually produced it."""

    draft: ModelDraft
    provider: str


class ChainedAnswerModel:
    """Try each provider in order within one shared deadline."""

    name = "chain"

    def __init__(
        self,
        members: Sequence[NamedAnswerModel],
        *,
        phase_seconds: float = ANSWER_PHASE_SECONDS,
        attempt_seconds: float = ANSWER_ATTEMPT_SECONDS,
    ) -> None:
        if not members:
            raise ValueError("an answer chain needs at least one provider")
        self._members = tuple(members)
        self._phase_seconds = phase_seconds
        self._attempt_seconds = attempt_seconds

    @property
    def providers(self) -> tuple[str, ...]:
        """The provider names in the order they will be tried."""

        return tuple(member.name for member in self._members)

    def answer(self, request: GroundedAnswerRequest) -> ModelDraft:
        """Return the first usable draft, or raise if every provider failed."""

        return self.answer_with_provider(request).draft

    def answer_with_provider(self, request: GroundedAnswerRequest) -> AnsweredBy:
        """Return the draft and the provider that produced it.

        The caller needs the provider name so that entailment verification can
        be run somewhere else. A model must not be the proof of its own output.
        """

        expires_at = time.monotonic() + self._phase_seconds
        last_error: Exception | None = None

        for member in self._members:
            remaining = expires_at - time.monotonic()
            if remaining <= 0:
                _LOGGER.warning("answer chain exhausted its budget before %s", member.name)
                break
            attempt = min(self._attempt_seconds, remaining)
            started = time.monotonic()
            try:
                draft = _call_within(member.model, request, attempt)
            except AnswerModelUnavailable as exc:
                # The reason is recorded, never the credential: adapters raise
                # with a description of the fault, not the request they sent.
                _LOGGER.warning(
                    "answer provider %s failed after %.1fs: %s",
                    member.name,
                    time.monotonic() - started,
                    exc,
                )
                last_error = exc
                continue
            except Exception as exc:  # pragma: no cover - defensive
                _LOGGER.warning("answer provider %s raised %s", member.name, type(exc).__name__)
                last_error = exc
                continue

            _LOGGER.info(
                "answer provider %s succeeded in %.1fs", member.name, time.monotonic() - started
            )
            return AnsweredBy(draft=draft, provider=member.name)

        raise AnswerModelUnavailable(
            f"every answer provider failed ({', '.join(self.providers)})"
        ) from last_error


def _call_within(
    model: LegalAnswerModel, request: GroundedAnswerRequest, seconds: float
) -> ModelDraft:
    """Invoke one provider, applying the per-attempt allowance if it accepts one."""

    deadline_aware = getattr(model, "answer_within", None)
    if callable(deadline_aware):
        result: ModelDraft = deadline_aware(request, deadline_seconds=seconds)
        return result
    return model.answer(request)

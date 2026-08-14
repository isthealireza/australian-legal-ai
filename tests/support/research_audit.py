"""Test-only in-memory research audit sinks. Never import from production wiring.

ADR 0013 §5: the Slice 1 audit sink is in-memory and test-harness-only. There is
no production wiring and no persistent audit storage.
"""

from __future__ import annotations

from legal_ai.research.audit import ResearchAuditEvent
from legal_ai.research.errors import ResearchAuditSinkUnavailable


class InMemoryResearchAuditSink:
    """Records audit events in memory for assertions."""

    def __init__(self) -> None:
        self.events: list[ResearchAuditEvent] = []

    def record(self, event: ResearchAuditEvent) -> None:
        self.events.append(event)


class UnavailableResearchAuditSink:
    """A sink that reports itself unavailable and records nothing."""

    def __init__(self) -> None:
        self.events: list[ResearchAuditEvent] = []

    def record(self, event: ResearchAuditEvent) -> None:
        del event
        raise ResearchAuditSinkUnavailable("audit sink is unavailable")


class FailingResearchAuditSink:
    """A sink whose write fails with an unexpected error."""

    def __init__(self) -> None:
        self.events: list[ResearchAuditEvent] = []

    def record(self, event: ResearchAuditEvent) -> None:
        del event
        raise RuntimeError("audit write failed")

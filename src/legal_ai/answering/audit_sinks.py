"""Audit sinks usable outside the test harness.

ADR 0013 section 5 left the Phase 4 sink in-memory and test-only. Serving the
research boundary over HTTP needs a sink that survives the request, so this
module adds two: one that appends structured JSON lines to an injected path,
and one that writes to the standard library logger.

Both raise on any failure. `WaResearchService` treats a raised error as
terminal `AUDIT_SINK_UNAVAILABLE`, so an unwritable audit trail stops the
answer rather than degrading it.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from ..research.audit import ResearchAuditEvent
from ..research.errors import ResearchAuditSinkUnavailable

_LOGGER = logging.getLogger("legal_ai.research.audit")


def _serialise(event: ResearchAuditEvent) -> str:
    """Render one audit event as a single deterministic JSON line."""

    return json.dumps(event.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


class JsonlResearchAuditSink:
    """Append audit events to a JSON Lines file beneath an injected path."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ResearchAuditSinkUnavailable("audit directory could not be created") from exc

    def record(self, event: ResearchAuditEvent) -> None:
        """Append one event, flushing to disk before returning."""

        line = _serialise(event)
        try:
            with self._lock, self._path.open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")
                handle.flush()
        except OSError as exc:
            raise ResearchAuditSinkUnavailable("audit event could not be written") from exc


class LoggingResearchAuditSink:
    """Emit audit events through the standard library logger."""

    def record(self, event: ResearchAuditEvent) -> None:
        """Log one event at INFO, or raise if logging itself fails."""

        try:
            _LOGGER.info("%s", _serialise(event))
        except Exception as exc:
            raise ResearchAuditSinkUnavailable("audit event could not be logged") from exc

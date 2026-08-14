"""Typed fail-closed errors for the Phase 4 WA research boundary."""


class ResearchError(Exception):
    """Base class for WA research boundary failures."""


class ResearchAuditSinkUnavailable(ResearchError):
    """The injected audit sink reported that it cannot accept events."""


class RecordedCorpusError(ResearchError):
    """A recorded fixture could not be loaded as a structurally usable record."""


class AmbiguousSelection(RecordedCorpusError):
    """More than one recorded source matched; no deterministic selection exists."""

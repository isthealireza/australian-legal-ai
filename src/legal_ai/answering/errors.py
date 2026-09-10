"""Typed fail-closed errors for the grounded answering boundary."""


class AnsweringError(Exception):
    """Base class for grounded answering failures."""


class AnswerModelUnavailable(AnsweringError):
    """The configured answer model could not produce a structured draft."""


class AuditSinkUnavailable(AnsweringError):
    """An audit sink reported that it cannot accept events."""

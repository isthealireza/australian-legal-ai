"""Typed failures for bounded EPUB structural extraction."""


class EpubParseError(Exception):
    """Base error for failures at the public EPUB parsing boundary."""


class EpubValidationError(EpubParseError):
    """The artifact or required EPUB structure was invalid."""


class EpubSecurityError(EpubParseError):
    """The EPUB violated a fail-closed archive or XML security rule."""


class EpubUnsupportedFeatureError(EpubParseError):
    """The EPUB uses a feature outside the deliberately bounded subset."""

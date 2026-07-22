"""Public secure EPUB structural extraction interface."""

from .epub import parse_epub
from .errors import (
    EpubParseError,
    EpubSecurityError,
    EpubUnsupportedFeatureError,
    EpubValidationError,
)
from .models import (
    EpubParseLimits,
    EpubSpineDocument,
    EpubTextBlock,
    ParsedEpubDocument,
)

__all__ = [
    "EpubParseError",
    "EpubParseLimits",
    "EpubSecurityError",
    "EpubSpineDocument",
    "EpubTextBlock",
    "EpubUnsupportedFeatureError",
    "EpubValidationError",
    "ParsedEpubDocument",
    "parse_epub",
]

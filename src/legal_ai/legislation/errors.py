"""Typed failures for deterministic legislation structure recognition."""


class LegislationStructureError(Exception):
    """Base error for failures at the public legislation-structure boundary."""


class LegislationStructureValidationError(LegislationStructureError):
    """The supplied parsed document could not be structured safely."""

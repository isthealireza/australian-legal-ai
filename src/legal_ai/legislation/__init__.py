"""Public deterministic Commonwealth legislation structure interface."""

from .errors import LegislationStructureError, LegislationStructureValidationError
from .models import (
    LegislationStructureDiagnostic,
    LegislationStructureDiagnosticCode,
    StructuralRole,
    StructuredLegislationBlock,
    StructuredLegislationDocument,
)
from .structure import structure_legislation

__all__ = [
    "LegislationStructureDiagnostic",
    "LegislationStructureDiagnosticCode",
    "LegislationStructureError",
    "LegislationStructureValidationError",
    "StructuralRole",
    "StructuredLegislationBlock",
    "StructuredLegislationDocument",
    "structure_legislation",
]

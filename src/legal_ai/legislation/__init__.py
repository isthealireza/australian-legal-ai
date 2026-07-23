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
from .subsection_models import (
    LegislationSubstructureDiagnostic,
    LegislationSubstructureDiagnosticCode,
    SubstructuredLegislationBlock,
    SubstructuredLegislationDocument,
    SubstructureRole,
)
from .subsections import (
    LegislationSubstructureError,
    LegislationSubstructureValidationError,
    structure_legislation_subsections,
)

__all__ = [
    "LegislationStructureDiagnostic",
    "LegislationStructureDiagnosticCode",
    "LegislationStructureError",
    "LegislationStructureValidationError",
    "LegislationSubstructureDiagnostic",
    "LegislationSubstructureDiagnosticCode",
    "LegislationSubstructureError",
    "LegislationSubstructureValidationError",
    "StructuralRole",
    "StructuredLegislationBlock",
    "StructuredLegislationDocument",
    "SubstructuredLegislationBlock",
    "SubstructuredLegislationDocument",
    "SubstructureRole",
    "structure_legislation",
    "structure_legislation_subsections",
]

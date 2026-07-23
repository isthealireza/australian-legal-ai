"""Public deterministic Commonwealth legislation structure interface."""

from .errors import LegislationStructureError, LegislationStructureValidationError
from .models import (
    LegislationStructureDiagnostic,
    LegislationStructureDiagnosticCode,
    StructuralRole,
    StructuredLegislationBlock,
    StructuredLegislationDocument,
)
from .paragraph_models import (
    LegislationParagraphDiagnostic,
    LegislationParagraphDiagnosticCode,
    ParagraphRole,
    ParagraphStructuredLegislationBlock,
    ParagraphStructuredLegislationDocument,
)
from .paragraphs import (
    LegislationParagraphError,
    LegislationParagraphValidationError,
    structure_legislation_paragraphs,
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
    "LegislationParagraphDiagnostic",
    "LegislationParagraphDiagnosticCode",
    "LegislationParagraphError",
    "LegislationParagraphValidationError",
    "LegislationStructureDiagnostic",
    "LegislationStructureDiagnosticCode",
    "LegislationStructureError",
    "LegislationStructureValidationError",
    "LegislationSubstructureDiagnostic",
    "LegislationSubstructureDiagnosticCode",
    "LegislationSubstructureError",
    "LegislationSubstructureValidationError",
    "ParagraphRole",
    "ParagraphStructuredLegislationBlock",
    "ParagraphStructuredLegislationDocument",
    "StructuralRole",
    "StructuredLegislationBlock",
    "StructuredLegislationDocument",
    "SubstructuredLegislationBlock",
    "SubstructuredLegislationDocument",
    "SubstructureRole",
    "structure_legislation",
    "structure_legislation_paragraphs",
    "structure_legislation_subsections",
]

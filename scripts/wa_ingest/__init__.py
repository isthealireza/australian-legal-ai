"""Operator tooling for staging one official WA source into the corpus.

This package is **operator tooling, not product code**. It deliberately lives
under `scripts/` rather than `src/legal_ai/` so that the product package never
gains an ingestion, extraction or filesystem-capture capability
(`PROJECT_GOVERNANCE.md` §7, `ENGINEERING_WORKFLOW.md` §13).

Two properties are load-bearing:

- **Nothing here reaches the network.** `stage` takes a file the operator has
  already downloaded from an official source. The act of capture stays with a
  human, so no code path in this repository can fetch legislation.
- **Nothing here promotes on its own judgement.** Promotion into the active
  corpus root refuses unless every precondition holds, including an owner
  approval record (gate G1) bound to the exact URL, version, currency date and
  retrieval timestamp.

See `docs/adr/0021-e2-wa-staging-pipeline.md`.
"""

from scripts.wa_ingest.extraction import (
    ExtractionTool,
    build_sections_file,
    normalise_extracted_text,
)
from scripts.wa_ingest.promotion import (
    PromotionRefusal,
    check_promotion,
    promote,
)
from scripts.wa_ingest.staging import (
    SourceIdentity,
    StagingLayout,
    build_manifest,
    compute_digest,
    slug_for_title,
)

__all__ = [
    "ExtractionTool",
    "PromotionRefusal",
    "SourceIdentity",
    "StagingLayout",
    "build_manifest",
    "build_sections_file",
    "check_promotion",
    "compute_digest",
    "normalise_extracted_text",
    "promote",
    "slug_for_title",
]

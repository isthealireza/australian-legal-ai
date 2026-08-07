from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest

from legal_ai.provenance import ArtifactRegistry, StoredArtifact
from legal_ai.provenance.errors import ProvenanceIntegrityConflict


def test_registry_rejects_malformed_verified_result_before_sql() -> None:
    connection = Mock()
    artifact = StoredArtifact(
        sha256="not-a-hash", byte_size=1, storage_key="bad", path=Path("unused")
    )
    with pytest.raises(ProvenanceIntegrityConflict):
        ArtifactRegistry().register(connection, artifact, media_type="text/plain")
    connection.execute.assert_not_called()


def test_registry_compatibility_is_exact() -> None:
    existing = {"sha256": "a" * 64, "byte_size": 1, "media_type": "text/plain"}
    ArtifactRegistry.require_compatible(cast(Any, existing), existing)
    with pytest.raises(ProvenanceIntegrityConflict, match="media_type"):
        ArtifactRegistry.require_compatible(
            cast(Any, existing), {**existing, "media_type": "image/png"}
        )

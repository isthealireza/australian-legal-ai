"""Neutral registration of immutable content-addressed artifact rows."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from sqlalchemy import Connection, RowMapping, select
from sqlalchemy.dialects.postgresql import insert

from legal_ai.db import artifacts

from .content_store import StoredArtifact
from .errors import ProvenanceIntegrityConflict
from .models import validate_sha256


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    sha256: str
    byte_size: int
    media_type: str
    storage_key: str


class ArtifactRegistry:
    """Register verified artifacts inside a caller-managed transaction."""

    def register(
        self,
        connection: Connection,
        artifact: StoredArtifact,
        *,
        media_type: str,
    ) -> ArtifactRecord:
        try:
            validate_sha256(artifact.sha256)
        except ValueError as exc:
            raise ProvenanceIntegrityConflict("artifact SHA-256 is malformed") from exc
        expected_key = f"sha256/{artifact.sha256[:2]}/{artifact.sha256[2:4]}/{artifact.sha256}.blob"
        if (
            artifact.byte_size <= 0
            or artifact.storage_key != expected_key
            or not media_type.strip()
        ):
            raise ProvenanceIntegrityConflict("artifact metadata is invalid")
        submitted = {
            "sha256": artifact.sha256,
            "byte_size": artifact.byte_size,
            "media_type": media_type,
            "storage_key": artifact.storage_key,
        }
        connection.execute(
            insert(artifacts)
            .values(**submitted)
            .on_conflict_do_nothing(index_elements=[artifacts.c.sha256])
        )
        existing = (
            connection.execute(select(artifacts).where(artifacts.c.sha256 == artifact.sha256))
            .mappings()
            .one()
        )
        self.require_compatible(existing, submitted)
        return ArtifactRecord(
            sha256=cast(str, existing["sha256"]),
            byte_size=cast(int, existing["byte_size"]),
            media_type=cast(str, existing["media_type"]),
            storage_key=cast(str, existing["storage_key"]),
        )

    @staticmethod
    def require_compatible(existing: RowMapping, submitted: Mapping[str, object]) -> None:
        conflicts = sorted(key for key, value in submitted.items() if existing[key] != value)
        if conflicts:
            raise ProvenanceIntegrityConflict(f"artifact conflicts on {', '.join(conflicts)}")

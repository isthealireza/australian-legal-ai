"""Fail-closed errors for immutable provenance capture."""


class ProvenanceError(Exception):
    """Base error for provenance storage failures."""


class ArtifactStoreError(ProvenanceError):
    """Base error for local artifact store failures."""


class ArtifactValidationError(ArtifactStoreError):
    """Artifact input did not satisfy the bounded storage contract."""


class ArtifactIntegrityError(ArtifactStoreError):
    """Stored bytes could not be proved identical to the expected artifact."""


class ArtifactPathError(ArtifactStoreError):
    """A derived artifact path escaped the configured storage root."""


class ArtifactPublicationError(ArtifactStoreError):
    """An artifact could not be published or its temporary file cleaned safely."""


class ProvenanceIntegrityConflict(ProvenanceError):
    """An immutable database identity conflicted with submitted provenance."""

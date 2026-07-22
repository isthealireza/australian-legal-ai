"""SQLAlchemy Core schema for immutable provenance metadata."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

metadata = MetaData()

artifacts = Table(
    "provenance_artifacts",
    metadata,
    Column("sha256", String(64), primary_key=True),
    Column("byte_size", BigInteger, nullable=False),
    Column("media_type", String(255), nullable=False),
    Column("storage_key", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    CheckConstraint(
        "sha256 ~ '^[0-9a-f]{64}$'",
        name="ck_provenance_artifacts_sha256_lower_hex",
    ),
    CheckConstraint(
        "byte_size > 0",
        name="ck_provenance_artifacts_byte_size_positive",
    ),
    CheckConstraint(
        "storage_key = "
        "'sha256/' || substring(sha256 from 1 for 2) || '/' || "
        "substring(sha256 from 3 for 2) || '/' || sha256 || '.blob'",
        name="ck_provenance_artifacts_storage_key_deterministic",
    ),
    UniqueConstraint(
        "storage_key",
        name="uq_provenance_artifacts_storage_key",
    ),
)

source_document_captures = Table(
    "source_document_captures",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("source_system", String(32), nullable=False),
    Column("title_id", String(11), nullable=False),
    Column("register_id", String(11), nullable=False),
    Column("official_document_id", String(255), nullable=False),
    Column("official_source_url", Text, nullable=False),
    Column("document_format", String(16), nullable=False),
    Column("volume", Integer, nullable=True),
    Column("retrieved_at", DateTime(timezone=True), nullable=False),
    Column("response_content_type", String(255), nullable=False),
    Column("etag", Text, nullable=True),
    Column("last_modified", Text, nullable=True),
    Column(
        "artifact_sha256",
        String(64),
        ForeignKey("provenance_artifacts.sha256", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    CheckConstraint(
        "source_system = 'federal_register'",
        name="ck_source_document_captures_source_system",
    ),
    CheckConstraint(
        "document_format IN ('Word', 'Pdf', 'Epub', 'NameOnly')",
        name="ck_source_document_captures_document_format",
    ),
    CheckConstraint(
        "volume IS NULL OR volume >= 0",
        name="ck_source_document_captures_volume_nonnegative",
    ),
    UniqueConstraint(
        "source_system",
        "official_document_id",
        name="uq_source_document_captures_source_document",
    ),
)

Index(
    "ix_source_document_captures_artifact_sha256",
    source_document_captures.c.artifact_sha256,
)
Index(
    "ix_source_document_captures_title_register",
    source_document_captures.c.title_id,
    source_document_captures.c.register_id,
)

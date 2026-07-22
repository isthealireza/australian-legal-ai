"""Create immutable provenance metadata tables.

Revision ID: 0004_immutable_provenance
Revises: None
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_immutable_provenance"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create only the immutable artifact and source-capture metadata tables."""

    op.create_table(
        "provenance_artifacts",
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "byte_size > 0",
            name="ck_provenance_artifacts_byte_size_positive",
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_provenance_artifacts_sha256_lower_hex",
        ),
        sa.CheckConstraint(
            "storage_key = "
            "'sha256/' || substring(sha256 from 1 for 2) || '/' || "
            "substring(sha256 from 3 for 2) || '/' || sha256 || '.blob'",
            name="ck_provenance_artifacts_storage_key_deterministic",
        ),
        sa.PrimaryKeyConstraint("sha256"),
        sa.UniqueConstraint(
            "storage_key",
            name="uq_provenance_artifacts_storage_key",
        ),
    )

    op.create_table(
        "source_document_captures",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("title_id", sa.String(length=11), nullable=False),
        sa.Column("register_id", sa.String(length=11), nullable=False),
        sa.Column("official_document_id", sa.String(length=255), nullable=False),
        sa.Column("official_source_url", sa.Text(), nullable=False),
        sa.Column("document_format", sa.String(length=16), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_content_type", sa.String(length=255), nullable=False),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "document_format IN ('Word', 'Pdf', 'Epub', 'NameOnly')",
            name="ck_source_document_captures_document_format",
        ),
        sa.CheckConstraint(
            "source_system = 'federal_register'",
            name="ck_source_document_captures_source_system",
        ),
        sa.CheckConstraint(
            "volume IS NULL OR volume >= 0",
            name="ck_source_document_captures_volume_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_sha256"],
            ["provenance_artifacts.sha256"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "official_document_id",
            name="uq_source_document_captures_source_document",
        ),
    )
    op.create_index(
        "ix_source_document_captures_artifact_sha256",
        "source_document_captures",
        ["artifact_sha256"],
        unique=False,
    )
    op.create_index(
        "ix_source_document_captures_title_register",
        "source_document_captures",
        ["title_id", "register_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove only indexes and tables created by this revision."""

    op.drop_index(
        "ix_source_document_captures_title_register",
        table_name="source_document_captures",
    )
    op.drop_index(
        "ix_source_document_captures_artifact_sha256",
        table_name="source_document_captures",
    )
    op.drop_table("source_document_captures")
    op.drop_table("provenance_artifacts")

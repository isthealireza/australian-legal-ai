"""SQLAlchemy Core tables for the Phase 3 matter evidence vault."""

# ruff: noqa: E501

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from legal_ai.db.schema import metadata

casework_evidence_records = Table(
    "casework_evidence_records",
    metadata,
    Column("evidence_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("artifact_sha256", String(64), nullable=False),
    Column("evidence_kind", String(16), nullable=False),
    Column("evidence_role", String(16), nullable=False),
    Column("caller_filename", Text, nullable=False),
    Column("declared_media_type", String(64), nullable=False),
    Column("detected_media_type", String(64), nullable=False),
    Column("expected_byte_size", Integer, nullable=False),
    Column(
        "supplied_unverified_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    ),
    Column("review_status", String(32), nullable=False, server_default=text("'UPLOADED'")),
    Column("row_version", Integer, nullable=False, server_default=text("1")),
    Column("registered_by", String(128), nullable=False),
    Column("registered_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("reviewed_by", String(128), nullable=True),
    Column("reviewed_at", DateTime(timezone=True), nullable=True),
    Column("review_reason", Text, nullable=True),
    PrimaryKeyConstraint("evidence_id", name="pk_casework_evidence_records"),
    ForeignKeyConstraint(
        ["matter_id"],
        ["casework_matters.matter_id"],
        name="fk_evidence_records_matter",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["artifact_sha256"],
        ["provenance_artifacts.sha256"],
        name="fk_evidence_records_artifact",
        ondelete="RESTRICT",
    ),
    UniqueConstraint("matter_id", "artifact_sha256", name="uq_evidence_records_matter_artifact"),
    UniqueConstraint("matter_id", "evidence_id", name="uq_evidence_records_matter_id"),
    UniqueConstraint(
        "matter_id", "evidence_id", "artifact_sha256", name="uq_evidence_records_matter_id_hash"
    ),
    CheckConstraint("artifact_sha256 ~ '^[a-f0-9]{64}$'", name="ck_evidence_records_sha256"),
    CheckConstraint("evidence_kind IN ('IMAGE','VIDEO','TEXT')", name="ck_evidence_records_kind"),
    CheckConstraint("evidence_role IN ('ORIGINAL','DERIVED')", name="ck_evidence_records_role"),
    CheckConstraint(
        "review_status IN ('UPLOADED','REVIEW_ACCEPTED','REVIEW_REJECTED')",
        name="ck_evidence_records_review_status",
    ),
    CheckConstraint(
        "declared_media_type = detected_media_type", name="ck_evidence_records_media_match"
    ),
    CheckConstraint(
        "(evidence_kind='IMAGE' AND detected_media_type IN ('image/png','image/jpeg')) OR (evidence_kind='VIDEO' AND detected_media_type='video/mp4') OR (evidence_kind='TEXT' AND detected_media_type='text/plain')",
        name="ck_evidence_records_kind_media",
    ),
    CheckConstraint(
        "expected_byte_size > 0 AND expected_byte_size <= 104857600",
        name="ck_evidence_records_size",
    ),
    CheckConstraint(
        "octet_length(caller_filename) <= 255 AND char_length(btrim(caller_filename)) > 0",
        name="ck_evidence_records_filename",
    ),
    CheckConstraint(
        "pg_column_size(supplied_unverified_metadata) <= 4096",
        name="ck_evidence_records_metadata_size",
    ),
    CheckConstraint("row_version >= 1", name="ck_evidence_records_row_version"),
    CheckConstraint(
        "(review_status='UPLOADED' AND reviewed_by IS NULL AND reviewed_at IS NULL AND review_reason IS NULL) OR (review_status IN ('REVIEW_ACCEPTED','REVIEW_REJECTED') AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND char_length(btrim(review_reason)) > 0)",
        name="ck_evidence_records_review_fields",
    ),
)
Index("ix_evidence_records_matter", casework_evidence_records.c.matter_id)

casework_evidence_derivations = Table(
    "casework_evidence_derivations",
    metadata,
    Column("derivation_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("source_evidence_id", UUID(as_uuid=True), nullable=False),
    Column("source_artifact_sha256", String(64), nullable=False),
    Column("derived_evidence_id", UUID(as_uuid=True), nullable=False),
    Column("derived_artifact_sha256", String(64), nullable=False),
    Column("operation_code", String(128), nullable=False),
    Column("operation_version", String(128), nullable=False),
    Column("processor_version", String(128), nullable=False),
    Column("parameters_sha256", String(64), nullable=True),
    Column("deterministic", Boolean, nullable=False),
    Column("created_by", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("derivation_id", name="pk_casework_evidence_derivations"),
    UniqueConstraint("matter_id", "derived_evidence_id", name="uq_evidence_derivations_derived"),
    ForeignKeyConstraint(
        ["matter_id", "source_evidence_id", "source_artifact_sha256"],
        [
            "casework_evidence_records.matter_id",
            "casework_evidence_records.evidence_id",
            "casework_evidence_records.artifact_sha256",
        ],
        name="fk_evidence_derivations_source",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["matter_id", "derived_evidence_id", "derived_artifact_sha256"],
        [
            "casework_evidence_records.matter_id",
            "casework_evidence_records.evidence_id",
            "casework_evidence_records.artifact_sha256",
        ],
        name="fk_evidence_derivations_derived",
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        "source_evidence_id <> derived_evidence_id", name="ck_evidence_derivations_distinct_ids"
    ),
    CheckConstraint(
        "source_artifact_sha256 <> derived_artifact_sha256",
        name="ck_evidence_derivations_distinct_hashes",
    ),
    CheckConstraint(
        "parameters_sha256 IS NULL OR parameters_sha256 ~ '^[a-f0-9]{64}$'",
        name="ck_evidence_derivations_parameters_sha256",
    ),
    CheckConstraint(
        "char_length(btrim(operation_code)) > 0 AND char_length(btrim(operation_version)) > 0 AND char_length(btrim(processor_version)) > 0",
        name="ck_evidence_derivations_identifiers",
    ),
)

casework_evidence_checklist_links = Table(
    "casework_evidence_checklist_links",
    metadata,
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("evidence_id", UUID(as_uuid=True), nullable=False),
    Column("playbook_version_id", UUID(as_uuid=True), nullable=False),
    Column("checklist_item_id", String(128), nullable=False),
    Column("linked_by", String(128), nullable=False),
    Column("linked_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint(
        "matter_id",
        "evidence_id",
        "playbook_version_id",
        "checklist_item_id",
        name="pk_casework_evidence_checklist_links",
    ),
    ForeignKeyConstraint(
        ["matter_id", "evidence_id"],
        ["casework_evidence_records.matter_id", "casework_evidence_records.evidence_id"],
        name="fk_evidence_checklist_links_evidence",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["playbook_version_id"],
        ["playbook_versions.playbook_version_id"],
        name="fk_evidence_checklist_links_version",
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        "char_length(btrim(checklist_item_id)) > 0", name="ck_evidence_checklist_links_item"
    ),
)

EVIDENCE_TABLES = (
    casework_evidence_records,
    casework_evidence_derivations,
    casework_evidence_checklist_links,
)
assert isinstance(metadata, MetaData)

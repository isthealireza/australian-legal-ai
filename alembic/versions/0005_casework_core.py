"""Create Phase 1 Generic Casework Core tables.

Revision ID: 0005_casework_core
Revises: 0004_immutable_provenance
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_casework_core"
down_revision: str | None = "0004_immutable_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JURISDICTIONS = (
    "'AU-CTH', 'AU-ACT', 'AU-NSW', 'AU-NT', 'AU-QLD', "
    "'AU-SA', 'AU-TAS', 'AU-VIC', 'AU-WA', 'UNKNOWN'"
)
_MATTER_STATUSES = (
    "'INTAKE_INCOMPLETE', 'INTAKE_COMPLETE', 'RESEARCH_AND_DRAFT_ONLY', "
    "'ACTIVE', 'WAITING', 'HUMAN_REVIEW_REQUIRED', 'RESOLVED', 'CLOSED'"
)
_CASE_TYPES = "'UNASSIGNED', 'UNSUPPORTED', 'SUPPORTED_PENDING_PLAYBOOK'"
_RISK_LEVELS = "'R0', 'R1', 'R2', 'R3', 'R4'"
_AUTHORITIES = "'L0', 'L1', 'L2'"
_PARTY_ENTITY_TYPES = "'NATURAL_PERSON', 'ORGANISATION'"
_PARTY_ROLES = (
    "'PRIMARY_SUBJECT', 'CLIENT', 'COUNTERPARTY', 'WITNESS', 'INSURER', "
    "'GOVERNMENT_AGENCY', 'REPRESENTATIVE', 'OTHER'"
)
_FACT_KINDS = (
    "'USER_ALLEGATION', 'OBSERVED', 'IMPORTED_STATEMENT', 'DERIVED', 'ASSUMPTION', 'UNKNOWN_ITEM'"
)
_FACT_STATUSES = "'ASSERTED', 'DISPUTED', 'VERIFIED', 'UNKNOWN'"
_VERIFICATION_METHODS = "'OPERATOR_ATTESTATION', 'DOCUMENT_REVIEW', 'THIRD_PARTY_CONFIRMATION'"
_ISSUE_TYPES = "'FACTUAL', 'LEGAL_QUESTION', 'ADMINISTRATIVE'"
_ISSUE_STATUSES = "'OPEN', 'MONITORING', 'RESOLVED', 'WITHDRAWN'"
_TASK_STATUSES = "'OPEN', 'DONE', 'CANCELLED'"
_DEADLINE_PRECISIONS = "'DATE', 'DATETIME'"
_DEADLINE_STATUSES = "'OPEN', 'MET', 'CANCELLED'"
_DEADLINE_CONFIDENCES = "'LOW', 'MEDIUM', 'HIGH'"
_CONFIRMATION_METHODS = "'OPERATOR_ATTESTATION', 'EXTERNAL_NOTICE_RECORDED'"


def upgrade() -> None:
    """Create casework sequence, tables, immutability function, and triggers."""

    op.execute("CREATE SEQUENCE casework_matter_reference_seq")

    op.create_table(
        "casework_matters",
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("jurisdiction", sa.String(length=16), nullable=False),
        sa.Column("case_type", sa.String(length=64), nullable=False),
        sa.Column("risk_level", sa.String(length=8), nullable=False),
        sa.Column("action_authority_ceiling", sa.String(length=8), nullable=False),
        sa.Column(
            "row_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("updated_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"status IN ({_MATTER_STATUSES})",
            name="ck_casework_matters_status",
        ),
        sa.CheckConstraint(
            f"jurisdiction IN ({_JURISDICTIONS})",
            name="ck_casework_matters_jurisdiction",
        ),
        sa.CheckConstraint(
            f"case_type IN ({_CASE_TYPES})",
            name="ck_casework_matters_case_type",
        ),
        sa.CheckConstraint(
            f"risk_level IN ({_RISK_LEVELS})",
            name="ck_casework_matters_risk_level",
        ),
        sa.CheckConstraint(
            f"action_authority_ceiling IN ({_AUTHORITIES})",
            name="ck_casework_matters_authority_ceiling",
        ),
        sa.CheckConstraint(
            "row_version >= 1",
            name="ck_casework_matters_row_version_positive",
        ),
        sa.CheckConstraint(
            "char_length(btrim(title)) > 0",
            name="ck_casework_matters_title_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(created_by)) > 0",
            name="ck_casework_matters_created_by_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(updated_by)) > 0",
            name="ck_casework_matters_updated_by_nonblank",
        ),
        sa.PrimaryKeyConstraint("matter_id", name="pk_casework_matters"),
        sa.UniqueConstraint("reference", name="uq_casework_matters_reference"),
    )

    op.create_table(
        "casework_parties",
        sa.Column("party_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"entity_type IN ({_PARTY_ENTITY_TYPES})",
            name="ck_casework_parties_entity_type",
        ),
        sa.CheckConstraint(
            "char_length(btrim(display_name)) > 0",
            name="ck_casework_parties_display_name_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["casework_matters.matter_id"],
            name="fk_casework_parties_matter_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("party_id", name="pk_casework_parties"),
        sa.UniqueConstraint(
            "matter_id",
            "party_id",
            name="uq_casework_parties_matter_party",
        ),
    )
    op.create_index(
        "ix_casework_parties_matter_id",
        "casework_parties",
        ["matter_id"],
        unique=False,
    )

    op.create_table(
        "casework_party_roles",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("party_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"role IN ({_PARTY_ROLES})",
            name="ck_casework_party_roles_role",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id", "party_id"],
            ["casework_parties.matter_id", "casework_parties.party_id"],
            name="fk_casework_party_roles_party",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("role_id", name="pk_casework_party_roles"),
        sa.UniqueConstraint(
            "matter_id",
            "party_id",
            "role",
            name="uq_casework_party_roles_matter_party_role",
        ),
    )

    op.create_table(
        "casework_fact_items",
        sa.Column("fact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("source_channel", sa.String(length=64), nullable=True),
        sa.Column("verified_by", sa.String(length=128), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_method", sa.String(length=64), nullable=True),
        sa.Column("verification_source_ref", sa.Text(), nullable=True),
        sa.Column("verification_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"kind IN ({_FACT_KINDS})",
            name="ck_casework_fact_items_kind",
        ),
        sa.CheckConstraint(
            f"status IN ({_FACT_STATUSES})",
            name="ck_casework_fact_items_status",
        ),
        sa.CheckConstraint(
            "char_length(btrim(statement)) > 0",
            name="ck_casework_fact_items_statement_nonblank",
        ),
        sa.CheckConstraint(
            "("
            "status <> 'VERIFIED' AND verified_by IS NULL AND verified_at IS NULL "
            "AND verification_method IS NULL AND verification_source_ref IS NULL "
            "AND verification_note IS NULL"
            ") OR ("
            "status = 'VERIFIED' AND verified_by IS NOT NULL AND verified_at IS NOT NULL "
            "AND verification_method IS NOT NULL "
            "AND char_length(btrim(verification_note)) > 0 "
            "AND ("
            "(verification_method = 'OPERATOR_ATTESTATION') OR "
            "(verification_method IN ('DOCUMENT_REVIEW', 'THIRD_PARTY_CONFIRMATION') "
            "AND verification_source_ref IS NOT NULL "
            "AND char_length(btrim(verification_source_ref)) > 0)"
            ")"
            ")",
            name="ck_casework_fact_items_verification_fields",
        ),
        sa.CheckConstraint(
            f"verification_method IS NULL OR verification_method IN ({_VERIFICATION_METHODS})",
            name="ck_casework_fact_items_verification_method",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["casework_matters.matter_id"],
            name="fk_casework_fact_items_matter_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("fact_id", name="pk_casework_fact_items"),
    )
    op.create_index(
        "ix_casework_fact_items_matter_id",
        "casework_fact_items",
        ["matter_id"],
        unique=False,
    )

    op.create_table(
        "casework_issues",
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issue_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("question_or_topic", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"issue_type IN ({_ISSUE_TYPES})",
            name="ck_casework_issues_issue_type",
        ),
        sa.CheckConstraint(
            f"status IN ({_ISSUE_STATUSES})",
            name="ck_casework_issues_status",
        ),
        sa.CheckConstraint(
            "char_length(btrim(question_or_topic)) > 0",
            name="ck_casework_issues_topic_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["casework_matters.matter_id"],
            name="fk_casework_issues_matter_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("issue_id", name="pk_casework_issues"),
    )
    op.create_index(
        "ix_casework_issues_matter_id",
        "casework_issues",
        ["matter_id"],
        unique=False,
    )

    op.create_table(
        "casework_deadlines",
        sa.Column("deadline_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_description", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("jurisdiction", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("responsible_actor", sa.String(length=128), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("precision", sa.String(length=16), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "human_confirmation_required",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("confirmed_by", sa.String(length=128), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmation_method", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"jurisdiction IN ({_JURISDICTIONS})",
            name="ck_casework_deadlines_jurisdiction",
        ),
        sa.CheckConstraint(
            f"confidence IN ({_DEADLINE_CONFIDENCES})",
            name="ck_casework_deadlines_confidence",
        ),
        sa.CheckConstraint(
            f"precision IN ({_DEADLINE_PRECISIONS})",
            name="ck_casework_deadlines_precision",
        ),
        sa.CheckConstraint(
            f"status IN ({_DEADLINE_STATUSES})",
            name="ck_casework_deadlines_status",
        ),
        sa.CheckConstraint(
            "("
            "precision = 'DATE' AND due_date IS NOT NULL AND due_at IS NULL"
            ") OR ("
            "precision = 'DATETIME' AND due_at IS NOT NULL AND due_date IS NULL"
            ")",
            name="ck_casework_deadlines_precision_due",
        ),
        sa.CheckConstraint(
            "("
            "confirmed_by IS NULL AND confirmed_at IS NULL "
            "AND confirmation_method IS NULL"
            ") OR ("
            "confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmation_method IS NOT NULL "
            f"AND confirmation_method IN ({_CONFIRMATION_METHODS})"
            ")",
            name="ck_casework_deadlines_confirmation_fields",
        ),
        sa.CheckConstraint(
            "char_length(btrim(source_description)) > 0",
            name="ck_casework_deadlines_source_description_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(timezone)) > 0",
            name="ck_casework_deadlines_timezone_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["casework_matters.matter_id"],
            name="fk_casework_deadlines_matter_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("deadline_id", name="pk_casework_deadlines"),
        sa.UniqueConstraint(
            "matter_id",
            "deadline_id",
            name="uq_casework_deadlines_matter_deadline",
        ),
    )
    op.create_index(
        "ix_casework_deadlines_matter_id",
        "casework_deadlines",
        ["matter_id"],
        unique=False,
    )

    op.create_table(
        "casework_tasks",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("deadline_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"status IN ({_TASK_STATUSES})",
            name="ck_casework_tasks_status",
        ),
        sa.CheckConstraint(
            "char_length(btrim(title)) > 0",
            name="ck_casework_tasks_title_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["casework_matters.matter_id"],
            name="fk_casework_tasks_matter_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id", "deadline_id"],
            ["casework_deadlines.matter_id", "casework_deadlines.deadline_id"],
            name="fk_casework_tasks_deadline",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("task_id", name="pk_casework_tasks"),
    )
    op.create_index(
        "ix_casework_tasks_matter_id",
        "casework_tasks",
        ["matter_id"],
        unique=False,
    )

    op.create_table(
        "casework_audit_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source_channel", sa.String(length=64), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(btrim(actor)) > 0",
            name="ck_casework_audit_events_actor_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(event_type)) > 0",
            name="ck_casework_audit_events_event_type_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(entity_type)) > 0",
            name="ck_casework_audit_events_entity_type_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(source_channel)) > 0",
            name="ck_casework_audit_events_source_channel_nonblank",
        ),
        sa.CheckConstraint(
            "pg_column_size(metadata) <= 4096",
            name="ck_casework_audit_events_metadata_size",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["casework_matters.matter_id"],
            name="fk_casework_audit_events_matter_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_casework_audit_events"),
    )
    op.create_index(
        "ix_casework_audit_events_matter_occurred",
        "casework_audit_events",
        ["matter_id", "occurred_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION casework_audit_events_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'casework_audit_events are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_casework_audit_events_immutable_update
        BEFORE UPDATE ON casework_audit_events
        FOR EACH ROW
        EXECUTE FUNCTION casework_audit_events_immutable()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_casework_audit_events_immutable_delete
        BEFORE DELETE ON casework_audit_events
        FOR EACH ROW
        EXECUTE FUNCTION casework_audit_events_immutable()
        """
    )


def downgrade() -> None:
    """Drop casework triggers, function, tables, and sequence only."""

    op.execute(
        "DROP TRIGGER IF EXISTS trg_casework_audit_events_immutable_update ON casework_audit_events"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_casework_audit_events_immutable_delete ON casework_audit_events"
    )
    op.execute("DROP FUNCTION IF EXISTS casework_audit_events_immutable()")

    op.drop_index(
        "ix_casework_audit_events_matter_occurred",
        table_name="casework_audit_events",
    )
    op.drop_table("casework_audit_events")
    op.drop_index("ix_casework_tasks_matter_id", table_name="casework_tasks")
    op.drop_table("casework_tasks")
    op.drop_index("ix_casework_deadlines_matter_id", table_name="casework_deadlines")
    op.drop_table("casework_deadlines")
    op.drop_index("ix_casework_issues_matter_id", table_name="casework_issues")
    op.drop_table("casework_issues")
    op.drop_index("ix_casework_fact_items_matter_id", table_name="casework_fact_items")
    op.drop_table("casework_fact_items")
    op.drop_table("casework_party_roles")
    op.drop_index("ix_casework_parties_matter_id", table_name="casework_parties")
    op.drop_table("casework_parties")
    op.drop_table("casework_matters")
    op.execute("DROP SEQUENCE IF EXISTS casework_matter_reference_seq")

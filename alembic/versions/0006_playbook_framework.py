"""Create Phase 2 Versioned Playbook Framework tables and matter pin columns.

Revision ID: 0006_playbook_framework
Revises: 0005_casework_core
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_playbook_framework"
down_revision: str | None = "0005_casework_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CASE_TYPES_V1 = "'UNASSIGNED', 'UNSUPPORTED', 'SUPPORTED_PENDING_PLAYBOOK'"
_CASE_TYPES_V2 = (
    "'UNASSIGNED', 'UNSUPPORTED', 'SUPPORTED_PENDING_PLAYBOOK', 'MOTOR_VEHICLE_PROPERTY_DAMAGE'"
)
_PLAYBOOK_STATUSES = "'DRAFT', 'ACTIVE', 'RETIRED'"
_PLAYBOOK_AUDIT_EVENT_TYPES = (
    "'PLAYBOOK_DRAFT_CREATED', 'PLAYBOOK_DRAFT_UPDATED', 'PLAYBOOK_DRAFT_SEED_NOOP', "
    "'PLAYBOOK_ACTIVATION_DENIED', 'PLAYBOOK_ACTIVATED', 'PLAYBOOK_RETIRED'"
)
_EVALUATION_OUTCOMES = (
    "'NO_CANDIDATES', 'MULTIPLE_CANDIDATES', 'UNKNOWN_ELIGIBILITY', "
    "'BLOCKING_DISQUALIFIER', 'ASSIGNMENT_REJECTED', "
    "'BLOCKING_DISQUALIFIER_WHILE_PINNED', 'ASSIGNED', 'UPGRADED'"
)
_EVALUATION_REASONS = (
    "'NO_ACTIVE_MATCH', 'MULTIPLE_ACTIVE_MATCHES', 'UNKNOWN_MATERIAL_ELIGIBILITY', "
    "'DISQUALIFIER_MATCHED', 'HUMAN_REJECTED', 'HUMAN_ASSIGNED', 'HUMAN_UPGRADED', "
    "'CLOSED_MATTER', 'INCOMPATIBLE'"
)
_ELIGIBILITY_RESULTS = "'MATCH', 'UNKNOWN'"
_INTAKE_VALUE_TYPES = "'BOOLEAN', 'TEXT', 'DATE', 'ENUM'"
_CHECKLIST_STATUSES = (
    "'PROVIDED', 'MISSING', 'UNKNOWN', 'NOT_APPLICABLE', 'HUMAN_VERIFICATION_REQUIRED'"
)
_INTAKE_VALUE_XOR = (
    "("
    "(value_type = 'BOOLEAN' AND value_boolean IS NOT NULL "
    "AND value_text IS NULL AND value_date IS NULL AND value_enum_code IS NULL) OR "
    "(value_type = 'TEXT' AND value_text IS NOT NULL "
    "AND value_boolean IS NULL AND value_date IS NULL AND value_enum_code IS NULL "
    "AND char_length(value_text) <= 512) OR "
    "(value_type = 'DATE' AND value_date IS NOT NULL "
    "AND value_boolean IS NULL AND value_text IS NULL AND value_enum_code IS NULL) OR "
    "(value_type = 'ENUM' AND value_enum_code IS NOT NULL "
    "AND value_boolean IS NULL AND value_text IS NULL AND value_date IS NULL "
    "AND char_length(value_enum_code) <= 64)"
    ")"
)


def upgrade() -> None:
    """Create playbook tables, alter matters pin columns, and install guards."""

    op.create_table(
        "playbooks",
        sa.Column("playbook_key", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.CheckConstraint(
            "char_length(btrim(playbook_key)) > 0",
            name="ck_playbooks_playbook_key_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(display_name)) > 0",
            name="ck_playbooks_display_name_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(created_by)) > 0",
            name="ck_playbooks_created_by_nonblank",
        ),
        sa.PrimaryKeyConstraint("playbook_key", name="pk_playbooks"),
    )

    op.create_table(
        "playbook_versions",
        sa.Column("playbook_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("playbook_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("definition_json", postgresql.JSONB(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "row_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.String(length=128), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("activated_by", sa.String(length=128), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_by", sa.String(length=128), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retirement_reason_code", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"status IN ({_PLAYBOOK_STATUSES})",
            name="ck_playbook_versions_status",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_playbook_versions_version_positive",
        ),
        sa.CheckConstraint(
            "row_version >= 1",
            name="ck_playbook_versions_row_version_positive",
        ),
        sa.CheckConstraint(
            "pg_column_size(definition_json) <= 65536",
            name="ck_playbook_versions_definition_size",
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[a-f0-9]{64}$'",
            name="ck_playbook_versions_content_sha256",
        ),
        sa.CheckConstraint(
            "char_length(btrim(created_by)) > 0",
            name="ck_playbook_versions_created_by_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(updated_by)) > 0",
            name="ck_playbook_versions_updated_by_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["playbook_key"],
            ["playbooks.playbook_key"],
            name="fk_playbook_versions_playbook_key",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("playbook_version_id", name="pk_playbook_versions"),
        sa.UniqueConstraint(
            "playbook_key",
            "version",
            name="uq_playbook_versions_key_version",
        ),
    )

    op.add_column(
        "casework_matters",
        sa.Column(
            "assigned_playbook_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "casework_matters",
        sa.Column("playbook_assigned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "casework_matters",
        sa.Column("playbook_assigned_by", sa.String(length=128), nullable=True),
    )
    op.drop_constraint(
        "ck_casework_matters_case_type",
        "casework_matters",
        type_="check",
    )
    op.create_check_constraint(
        "ck_casework_matters_case_type",
        "casework_matters",
        f"case_type IN ({_CASE_TYPES_V2})",
    )
    op.create_unique_constraint(
        "uq_casework_matters_matter_pin",
        "casework_matters",
        ["matter_id", "assigned_playbook_version_id"],
    )
    op.create_foreign_key(
        "fk_casework_matters_assigned_playbook_version_id",
        "casework_matters",
        "playbook_versions",
        ["assigned_playbook_version_id"],
        ["playbook_version_id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "playbook_audit_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("playbook_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("playbook_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("row_version_after", sa.Integer(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"event_type IN ({_PLAYBOOK_AUDIT_EVENT_TYPES})",
            name="ck_playbook_audit_events_event_type",
        ),
        sa.CheckConstraint(
            "char_length(btrim(playbook_key)) > 0",
            name="ck_playbook_audit_events_playbook_key_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(actor)) > 0",
            name="ck_playbook_audit_events_actor_nonblank",
        ),
        sa.CheckConstraint(
            "pg_column_size(metadata) <= 4096",
            name="ck_playbook_audit_events_metadata_size",
        ),
        sa.ForeignKeyConstraint(
            ["playbook_version_id"],
            ["playbook_versions.playbook_version_id"],
            name="fk_playbook_audit_events_playbook_version_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_playbook_audit_events"),
    )

    op.create_table(
        "casework_playbook_evaluations",
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("outcome_code", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column(
            "selected_playbook_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("matter_row_version_observed", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            f"outcome_code IN ({_EVALUATION_OUTCOMES})",
            name="ck_casework_playbook_evaluations_outcome_code",
        ),
        sa.CheckConstraint(
            f"reason_code IN ({_EVALUATION_REASONS})",
            name="ck_casework_playbook_evaluations_reason_code",
        ),
        sa.CheckConstraint(
            "matter_row_version_observed >= 1",
            name="ck_casework_playbook_evaluations_matter_row_version",
        ),
        sa.CheckConstraint(
            "notes IS NULL OR char_length(notes) <= 512",
            name="ck_casework_playbook_evaluations_notes_length",
        ),
        sa.CheckConstraint(
            "char_length(btrim(actor)) > 0",
            name="ck_casework_playbook_evaluations_actor_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["casework_matters.matter_id"],
            name="fk_casework_playbook_evaluations_matter_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["selected_playbook_version_id"],
            ["playbook_versions.playbook_version_id"],
            name="fk_casework_playbook_evaluations_selected_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "evaluation_id",
            name="pk_casework_playbook_evaluations",
        ),
    )

    op.create_table(
        "casework_playbook_evaluation_candidates",
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("playbook_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("presentation_order", sa.Integer(), nullable=False),
        sa.Column("eligibility_result", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "presentation_order >= 1",
            name="ck_casework_playbook_evaluation_candidates_order",
        ),
        sa.CheckConstraint(
            f"eligibility_result IN ({_ELIGIBILITY_RESULTS})",
            name="ck_casework_playbook_evaluation_candidates_eligibility",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["casework_playbook_evaluations.evaluation_id"],
            name="fk_casework_playbook_evaluation_candidates_evaluation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["playbook_version_id"],
            ["playbook_versions.playbook_version_id"],
            name="fk_casework_playbook_evaluation_candidates_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "evaluation_id",
            "playbook_version_id",
            name="pk_casework_playbook_evaluation_candidates",
        ),
        sa.UniqueConstraint(
            "evaluation_id",
            "presentation_order",
            name="uq_casework_playbook_evaluation_candidates_order",
        ),
    )

    op.create_table(
        "casework_intake_answers",
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("playbook_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", sa.Text(), nullable=False),
        sa.Column("value_type", sa.Text(), nullable=False),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("value_enum_code", sa.Text(), nullable=True),
        sa.Column("answered_by", sa.String(length=128), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "row_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"value_type IN ({_INTAKE_VALUE_TYPES})",
            name="ck_casework_intake_answers_value_type",
        ),
        sa.CheckConstraint(
            _INTAKE_VALUE_XOR,
            name="ck_casework_intake_answers_value_xor",
        ),
        sa.CheckConstraint(
            "char_length(question_id) <= 64 AND char_length(btrim(question_id)) > 0",
            name="ck_casework_intake_answers_question_id",
        ),
        sa.CheckConstraint(
            "row_version >= 1",
            name="ck_casework_intake_answers_row_version_positive",
        ),
        sa.CheckConstraint(
            "char_length(btrim(answered_by)) > 0",
            name="ck_casework_intake_answers_answered_by_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id", "playbook_version_id"],
            [
                "casework_matters.matter_id",
                "casework_matters.assigned_playbook_version_id",
            ],
            name="fk_casework_intake_answers_matter_pin",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "matter_id",
            "playbook_version_id",
            "question_id",
            name="pk_casework_intake_answers",
        ),
    )

    op.create_table(
        "casework_intake_answers_history",
        sa.Column("history_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("playbook_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", sa.Text(), nullable=False),
        sa.Column("value_type", sa.Text(), nullable=False),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("value_enum_code", sa.Text(), nullable=True),
        sa.Column("answered_by", sa.String(length=128), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.String(length=128), nullable=False),
        sa.Column(
            "superseded_by_playbook_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "upgrade_correlation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"value_type IN ({_INTAKE_VALUE_TYPES})",
            name="ck_casework_intake_answers_history_value_type",
        ),
        sa.CheckConstraint(
            _INTAKE_VALUE_XOR,
            name="ck_casework_intake_answers_history_value_xor",
        ),
        sa.CheckConstraint(
            "char_length(question_id) <= 64 AND char_length(btrim(question_id)) > 0",
            name="ck_casework_intake_answers_history_question_id",
        ),
        sa.CheckConstraint(
            "row_version >= 1",
            name="ck_casework_intake_answers_history_row_version",
        ),
        sa.CheckConstraint(
            "char_length(btrim(answered_by)) > 0",
            name="ck_casework_intake_answers_history_answered_by_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(superseded_by)) > 0",
            name="ck_casework_intake_answers_history_superseded_by_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["casework_matters.matter_id"],
            name="fk_casework_intake_answers_history_matter_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["playbook_version_id"],
            ["playbook_versions.playbook_version_id"],
            name="fk_casework_intake_answers_history_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_playbook_version_id"],
            ["playbook_versions.playbook_version_id"],
            name="fk_casework_intake_answers_history_superseded_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "history_id",
            name="pk_casework_intake_answers_history",
        ),
    )

    op.create_table(
        "casework_checklist_states",
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("playbook_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checklist_item_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "row_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"status IN ({_CHECKLIST_STATUSES})",
            name="ck_casework_checklist_states_status",
        ),
        sa.CheckConstraint(
            "note IS NULL OR char_length(note) <= 512",
            name="ck_casework_checklist_states_note_length",
        ),
        sa.CheckConstraint(
            "char_length(checklist_item_id) <= 64 AND char_length(btrim(checklist_item_id)) > 0",
            name="ck_casework_checklist_states_item_id",
        ),
        sa.CheckConstraint(
            "row_version >= 1",
            name="ck_casework_checklist_states_row_version_positive",
        ),
        sa.CheckConstraint(
            "char_length(btrim(updated_by)) > 0",
            name="ck_casework_checklist_states_updated_by_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id", "playbook_version_id"],
            [
                "casework_matters.matter_id",
                "casework_matters.assigned_playbook_version_id",
            ],
            name="fk_casework_checklist_states_matter_pin",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "matter_id",
            "playbook_version_id",
            "checklist_item_id",
            name="pk_casework_checklist_states",
        ),
    )

    op.create_table(
        "casework_checklist_states_history",
        sa.Column("history_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("playbook_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checklist_item_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.String(length=128), nullable=False),
        sa.Column(
            "superseded_by_playbook_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "upgrade_correlation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"status IN ({_CHECKLIST_STATUSES})",
            name="ck_casework_checklist_states_history_status",
        ),
        sa.CheckConstraint(
            "note IS NULL OR char_length(note) <= 512",
            name="ck_casework_checklist_states_history_note_length",
        ),
        sa.CheckConstraint(
            "char_length(checklist_item_id) <= 64 AND char_length(btrim(checklist_item_id)) > 0",
            name="ck_casework_checklist_states_history_item_id",
        ),
        sa.CheckConstraint(
            "row_version >= 1",
            name="ck_casework_checklist_states_history_row_version",
        ),
        sa.CheckConstraint(
            "char_length(btrim(updated_by)) > 0",
            name="ck_casework_checklist_states_history_updated_by_nonblank",
        ),
        sa.CheckConstraint(
            "char_length(btrim(superseded_by)) > 0",
            name="ck_casework_checklist_states_history_superseded_by_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["matter_id"],
            ["casework_matters.matter_id"],
            name="fk_casework_checklist_states_history_matter_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["playbook_version_id"],
            ["playbook_versions.playbook_version_id"],
            name="fk_casework_checklist_states_history_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_playbook_version_id"],
            ["playbook_versions.playbook_version_id"],
            name="fk_casework_checklist_states_history_superseded_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "history_id",
            name="pk_casework_checklist_states_history",
        ),
    )

    op.execute(
        """
        CREATE FUNCTION playbook_versions_transition_guard()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status = 'DRAFT' AND NEW.status = 'DRAFT' THEN
                IF NEW.playbook_version_id IS DISTINCT FROM OLD.playbook_version_id
                   OR NEW.playbook_key IS DISTINCT FROM OLD.playbook_key
                   OR NEW.version IS DISTINCT FROM OLD.version
                   OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
                   OR NEW.created_by IS DISTINCT FROM OLD.created_by
                   OR NEW.created_at IS DISTINCT FROM OLD.created_at
                   OR NEW.activated_by IS DISTINCT FROM OLD.activated_by
                   OR NEW.activated_at IS DISTINCT FROM OLD.activated_at
                   OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
                   OR NEW.retired_by IS DISTINCT FROM OLD.retired_by
                   OR NEW.retired_at IS DISTINCT FROM OLD.retired_at
                   OR NEW.retirement_reason_code
                        IS DISTINCT FROM OLD.retirement_reason_code
                   OR NEW.row_version IS DISTINCT FROM (OLD.row_version + 1)
                THEN
                    RAISE EXCEPTION
                        'playbook_versions DRAFT content update violates transition guard';
                END IF;
                RETURN NEW;
            END IF;

            IF OLD.status = 'DRAFT' AND NEW.status = 'ACTIVE' THEN
                IF NEW.playbook_version_id IS DISTINCT FROM OLD.playbook_version_id
                   OR NEW.playbook_key IS DISTINCT FROM OLD.playbook_key
                   OR NEW.version IS DISTINCT FROM OLD.version
                   OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
                   OR NEW.definition_json IS DISTINCT FROM OLD.definition_json
                   OR NEW.content_sha256 IS DISTINCT FROM OLD.content_sha256
                   OR NEW.created_by IS DISTINCT FROM OLD.created_by
                   OR NEW.created_at IS DISTINCT FROM OLD.created_at
                   OR NEW.updated_by IS DISTINCT FROM OLD.updated_by
                   OR NEW.updated_at IS DISTINCT FROM OLD.updated_at
                   OR NEW.retired_by IS DISTINCT FROM OLD.retired_by
                   OR NEW.retired_at IS DISTINCT FROM OLD.retired_at
                   OR NEW.retirement_reason_code
                        IS DISTINCT FROM OLD.retirement_reason_code
                   OR NEW.row_version IS DISTINCT FROM (OLD.row_version + 1)
                THEN
                    RAISE EXCEPTION
                        'playbook_versions DRAFT to ACTIVE update violates transition guard';
                END IF;
                RETURN NEW;
            END IF;

            IF OLD.status = 'ACTIVE' AND NEW.status = 'RETIRED' THEN
                IF NEW.playbook_version_id IS DISTINCT FROM OLD.playbook_version_id
                   OR NEW.playbook_key IS DISTINCT FROM OLD.playbook_key
                   OR NEW.version IS DISTINCT FROM OLD.version
                   OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
                   OR NEW.definition_json IS DISTINCT FROM OLD.definition_json
                   OR NEW.content_sha256 IS DISTINCT FROM OLD.content_sha256
                   OR NEW.created_by IS DISTINCT FROM OLD.created_by
                   OR NEW.created_at IS DISTINCT FROM OLD.created_at
                   OR NEW.updated_by IS DISTINCT FROM OLD.updated_by
                   OR NEW.updated_at IS DISTINCT FROM OLD.updated_at
                   OR NEW.activated_by IS DISTINCT FROM OLD.activated_by
                   OR NEW.activated_at IS DISTINCT FROM OLD.activated_at
                   OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
                   OR NEW.row_version IS DISTINCT FROM (OLD.row_version + 1)
                THEN
                    RAISE EXCEPTION
                        'playbook_versions ACTIVE to RETIRED update violates transition guard';
                END IF;
                RETURN NEW;
            END IF;

            RAISE EXCEPTION
                'playbook_versions transition from % to % is not allowed',
                OLD.status,
                NEW.status;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_playbook_versions_transition_guard
        BEFORE UPDATE ON playbook_versions
        FOR EACH ROW
        EXECUTE FUNCTION playbook_versions_transition_guard()
        """
    )

    op.execute(
        """
        CREATE FUNCTION playbook_versions_delete_guard()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'playbook_versions deletes are not allowed for status %',
                OLD.status;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_playbook_versions_delete_guard
        BEFORE DELETE ON playbook_versions
        FOR EACH ROW
        EXECUTE FUNCTION playbook_versions_delete_guard()
        """
    )

    for table_name in (
        "playbook_audit_events",
        "casework_playbook_evaluations",
        "casework_playbook_evaluation_candidates",
        "casework_intake_answers_history",
        "casework_checklist_states_history",
    ):
        function_name = f"{table_name}_immutable"
        op.execute(
            f"""
            CREATE FUNCTION {function_name}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION '{table_name} are immutable';
            END;
            $$
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_immutable_update
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION {function_name}()
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_immutable_delete
            BEFORE DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION {function_name}()
            """
        )


def downgrade() -> None:
    """Drop playbook framework objects only when no playbook data remains."""

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM playbook_versions LIMIT 1)
               OR EXISTS (SELECT 1 FROM playbook_audit_events LIMIT 1)
               OR EXISTS (SELECT 1 FROM casework_playbook_evaluations LIMIT 1)
               OR EXISTS (
                    SELECT 1 FROM casework_playbook_evaluation_candidates LIMIT 1
               )
               OR EXISTS (SELECT 1 FROM casework_intake_answers LIMIT 1)
               OR EXISTS (SELECT 1 FROM casework_intake_answers_history LIMIT 1)
               OR EXISTS (SELECT 1 FROM casework_checklist_states LIMIT 1)
               OR EXISTS (SELECT 1 FROM casework_checklist_states_history LIMIT 1)
               OR EXISTS (
                    SELECT 1 FROM casework_matters
                    WHERE assigned_playbook_version_id IS NOT NULL
                    LIMIT 1
               )
            THEN
                RAISE EXCEPTION
                    'refusing to downgrade 0006_playbook_framework: playbook data present';
            END IF;
        END
        $$
        """
    )

    for table_name in (
        "casework_checklist_states_history",
        "casework_intake_answers_history",
        "casework_playbook_evaluation_candidates",
        "casework_playbook_evaluations",
        "playbook_audit_events",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable_update ON {table_name}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable_delete ON {table_name}")
        op.execute(f"DROP FUNCTION IF EXISTS {table_name}_immutable()")

    op.execute("DROP TRIGGER IF EXISTS trg_playbook_versions_delete_guard ON playbook_versions")
    op.execute("DROP TRIGGER IF EXISTS trg_playbook_versions_transition_guard ON playbook_versions")
    op.execute("DROP FUNCTION IF EXISTS playbook_versions_delete_guard()")
    op.execute("DROP FUNCTION IF EXISTS playbook_versions_transition_guard()")

    op.drop_table("casework_checklist_states_history")
    op.drop_table("casework_checklist_states")
    op.drop_table("casework_intake_answers_history")
    op.drop_table("casework_intake_answers")
    op.drop_table("casework_playbook_evaluation_candidates")
    op.drop_table("casework_playbook_evaluations")
    op.drop_table("playbook_audit_events")

    op.drop_constraint(
        "fk_casework_matters_assigned_playbook_version_id",
        "casework_matters",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_casework_matters_matter_pin",
        "casework_matters",
        type_="unique",
    )
    op.drop_constraint(
        "ck_casework_matters_case_type",
        "casework_matters",
        type_="check",
    )
    op.create_check_constraint(
        "ck_casework_matters_case_type",
        "casework_matters",
        f"case_type IN ({_CASE_TYPES_V1})",
    )
    op.drop_column("casework_matters", "playbook_assigned_by")
    op.drop_column("casework_matters", "playbook_assigned_at")
    op.drop_column("casework_matters", "assigned_playbook_version_id")

    op.drop_table("playbook_versions")
    op.drop_table("playbooks")

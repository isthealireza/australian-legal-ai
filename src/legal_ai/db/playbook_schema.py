"""SQLAlchemy Core tables for Phase 2 Versioned Playbook Framework."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKeyConstraint,
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

playbooks = Table(
    "playbooks",
    metadata,
    Column("playbook_key", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column("created_by", String(128), nullable=False),
    PrimaryKeyConstraint("playbook_key", name="pk_playbooks"),
    CheckConstraint(
        "char_length(btrim(playbook_key)) > 0",
        name="ck_playbooks_playbook_key_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(display_name)) > 0",
        name="ck_playbooks_display_name_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(created_by)) > 0",
        name="ck_playbooks_created_by_nonblank",
    ),
)

playbook_versions = Table(
    "playbook_versions",
    metadata,
    Column("playbook_version_id", UUID(as_uuid=True), nullable=False),
    Column("playbook_key", Text, nullable=False),
    Column("version", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("schema_version", Integer, nullable=False),
    Column("definition_json", JSONB, nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("row_version", Integer, nullable=False, server_default=text("1")),
    Column("created_by", String(128), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column("updated_by", String(128), nullable=False),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column("activated_by", String(128), nullable=True),
    Column("activated_at", DateTime(timezone=True), nullable=True),
    Column("effective_from", DateTime(timezone=True), nullable=True),
    Column("retired_by", String(128), nullable=True),
    Column("retired_at", DateTime(timezone=True), nullable=True),
    Column("retirement_reason_code", Text, nullable=True),
    PrimaryKeyConstraint("playbook_version_id", name="pk_playbook_versions"),
    ForeignKeyConstraint(
        ["playbook_key"],
        ["playbooks.playbook_key"],
        name="fk_playbook_versions_playbook_key",
        ondelete="RESTRICT",
    ),
    UniqueConstraint(
        "playbook_key",
        "version",
        name="uq_playbook_versions_key_version",
    ),
    CheckConstraint(
        f"status IN ({_PLAYBOOK_STATUSES})",
        name="ck_playbook_versions_status",
    ),
    CheckConstraint(
        "version > 0",
        name="ck_playbook_versions_version_positive",
    ),
    CheckConstraint(
        "row_version >= 1",
        name="ck_playbook_versions_row_version_positive",
    ),
    CheckConstraint(
        "pg_column_size(definition_json) <= 65536",
        name="ck_playbook_versions_definition_size",
    ),
    CheckConstraint(
        "content_sha256 ~ '^[a-f0-9]{64}$'",
        name="ck_playbook_versions_content_sha256",
    ),
    CheckConstraint(
        "char_length(btrim(created_by)) > 0",
        name="ck_playbook_versions_created_by_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(updated_by)) > 0",
        name="ck_playbook_versions_updated_by_nonblank",
    ),
)

playbook_audit_events = Table(
    "playbook_audit_events",
    metadata,
    Column("event_id", UUID(as_uuid=True), nullable=False),
    Column("playbook_key", Text, nullable=False),
    Column("version", Integer, nullable=False),
    Column("playbook_version_id", UUID(as_uuid=True), nullable=False),
    Column("actor", String(128), nullable=False),
    Column("event_type", Text, nullable=False),
    Column(
        "occurred_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column("correlation_id", UUID(as_uuid=True), nullable=True),
    Column("row_version_after", Integer, nullable=True),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    PrimaryKeyConstraint("event_id", name="pk_playbook_audit_events"),
    ForeignKeyConstraint(
        ["playbook_version_id"],
        ["playbook_versions.playbook_version_id"],
        name="fk_playbook_audit_events_playbook_version_id",
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        f"event_type IN ({_PLAYBOOK_AUDIT_EVENT_TYPES})",
        name="ck_playbook_audit_events_event_type",
    ),
    CheckConstraint(
        "char_length(btrim(playbook_key)) > 0",
        name="ck_playbook_audit_events_playbook_key_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(actor)) > 0",
        name="ck_playbook_audit_events_actor_nonblank",
    ),
    CheckConstraint(
        "pg_column_size(metadata) <= 4096",
        name="ck_playbook_audit_events_metadata_size",
    ),
)

casework_playbook_evaluations = Table(
    "casework_playbook_evaluations",
    metadata,
    Column("evaluation_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("actor", String(128), nullable=False),
    Column("outcome_code", Text, nullable=False),
    Column("reason_code", Text, nullable=False),
    Column("selected_playbook_version_id", UUID(as_uuid=True), nullable=True),
    Column("matter_row_version_observed", Integer, nullable=False),
    Column("notes", Text, nullable=True),
    Column("correlation_id", UUID(as_uuid=True), nullable=True),
    PrimaryKeyConstraint("evaluation_id", name="pk_casework_playbook_evaluations"),
    ForeignKeyConstraint(
        ["matter_id"],
        ["casework_matters.matter_id"],
        name="fk_casework_playbook_evaluations_matter_id",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["selected_playbook_version_id"],
        ["playbook_versions.playbook_version_id"],
        name="fk_casework_playbook_evaluations_selected_version",
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        f"outcome_code IN ({_EVALUATION_OUTCOMES})",
        name="ck_casework_playbook_evaluations_outcome_code",
    ),
    CheckConstraint(
        f"reason_code IN ({_EVALUATION_REASONS})",
        name="ck_casework_playbook_evaluations_reason_code",
    ),
    CheckConstraint(
        "matter_row_version_observed >= 1",
        name="ck_casework_playbook_evaluations_matter_row_version",
    ),
    CheckConstraint(
        "notes IS NULL OR char_length(notes) <= 512",
        name="ck_casework_playbook_evaluations_notes_length",
    ),
    CheckConstraint(
        "char_length(btrim(actor)) > 0",
        name="ck_casework_playbook_evaluations_actor_nonblank",
    ),
)

casework_playbook_evaluation_candidates = Table(
    "casework_playbook_evaluation_candidates",
    metadata,
    Column("evaluation_id", UUID(as_uuid=True), nullable=False),
    Column("playbook_version_id", UUID(as_uuid=True), nullable=False),
    Column("presentation_order", Integer, nullable=False),
    Column("eligibility_result", Text, nullable=False),
    PrimaryKeyConstraint(
        "evaluation_id",
        "playbook_version_id",
        name="pk_casework_playbook_evaluation_candidates",
    ),
    ForeignKeyConstraint(
        ["evaluation_id"],
        ["casework_playbook_evaluations.evaluation_id"],
        name="fk_casework_playbook_evaluation_candidates_evaluation",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["playbook_version_id"],
        ["playbook_versions.playbook_version_id"],
        name="fk_casework_playbook_evaluation_candidates_version",
        ondelete="RESTRICT",
    ),
    UniqueConstraint(
        "evaluation_id",
        "presentation_order",
        name="uq_casework_playbook_evaluation_candidates_order",
    ),
    CheckConstraint(
        "presentation_order >= 1",
        name="ck_casework_playbook_evaluation_candidates_order",
    ),
    CheckConstraint(
        f"eligibility_result IN ({_ELIGIBILITY_RESULTS})",
        name="ck_casework_playbook_evaluation_candidates_eligibility",
    ),
)

casework_intake_answers = Table(
    "casework_intake_answers",
    metadata,
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("playbook_version_id", UUID(as_uuid=True), nullable=False),
    Column("question_id", Text, nullable=False),
    Column("value_type", Text, nullable=False),
    Column("value_boolean", Boolean, nullable=True),
    Column("value_text", Text, nullable=True),
    Column("value_date", Date, nullable=True),
    Column("value_enum_code", Text, nullable=True),
    Column("answered_by", String(128), nullable=False),
    Column("answered_at", DateTime(timezone=True), nullable=False),
    Column("row_version", Integer, nullable=False, server_default=text("1")),
    PrimaryKeyConstraint(
        "matter_id",
        "playbook_version_id",
        "question_id",
        name="pk_casework_intake_answers",
    ),
    ForeignKeyConstraint(
        ["matter_id", "playbook_version_id"],
        [
            "casework_matters.matter_id",
            "casework_matters.assigned_playbook_version_id",
        ],
        name="fk_casework_intake_answers_matter_pin",
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        f"value_type IN ({_INTAKE_VALUE_TYPES})",
        name="ck_casework_intake_answers_value_type",
    ),
    CheckConstraint(
        _INTAKE_VALUE_XOR,
        name="ck_casework_intake_answers_value_xor",
    ),
    CheckConstraint(
        "char_length(question_id) <= 64 AND char_length(btrim(question_id)) > 0",
        name="ck_casework_intake_answers_question_id",
    ),
    CheckConstraint(
        "row_version >= 1",
        name="ck_casework_intake_answers_row_version_positive",
    ),
    CheckConstraint(
        "char_length(btrim(answered_by)) > 0",
        name="ck_casework_intake_answers_answered_by_nonblank",
    ),
)

casework_intake_answers_history = Table(
    "casework_intake_answers_history",
    metadata,
    Column("history_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("playbook_version_id", UUID(as_uuid=True), nullable=False),
    Column("question_id", Text, nullable=False),
    Column("value_type", Text, nullable=False),
    Column("value_boolean", Boolean, nullable=True),
    Column("value_text", Text, nullable=True),
    Column("value_date", Date, nullable=True),
    Column("value_enum_code", Text, nullable=True),
    Column("answered_by", String(128), nullable=False),
    Column("answered_at", DateTime(timezone=True), nullable=False),
    Column("row_version", Integer, nullable=False),
    Column("superseded_at", DateTime(timezone=True), nullable=False),
    Column("superseded_by", String(128), nullable=False),
    Column("superseded_by_playbook_version_id", UUID(as_uuid=True), nullable=False),
    Column("upgrade_correlation_id", UUID(as_uuid=True), nullable=False),
    PrimaryKeyConstraint("history_id", name="pk_casework_intake_answers_history"),
    ForeignKeyConstraint(
        ["matter_id"],
        ["casework_matters.matter_id"],
        name="fk_casework_intake_answers_history_matter_id",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["playbook_version_id"],
        ["playbook_versions.playbook_version_id"],
        name="fk_casework_intake_answers_history_version",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["superseded_by_playbook_version_id"],
        ["playbook_versions.playbook_version_id"],
        name="fk_casework_intake_answers_history_superseded_version",
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        f"value_type IN ({_INTAKE_VALUE_TYPES})",
        name="ck_casework_intake_answers_history_value_type",
    ),
    CheckConstraint(
        _INTAKE_VALUE_XOR,
        name="ck_casework_intake_answers_history_value_xor",
    ),
    CheckConstraint(
        "char_length(question_id) <= 64 AND char_length(btrim(question_id)) > 0",
        name="ck_casework_intake_answers_history_question_id",
    ),
    CheckConstraint(
        "row_version >= 1",
        name="ck_casework_intake_answers_history_row_version",
    ),
    CheckConstraint(
        "char_length(btrim(answered_by)) > 0",
        name="ck_casework_intake_answers_history_answered_by_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(superseded_by)) > 0",
        name="ck_casework_intake_answers_history_superseded_by_nonblank",
    ),
)

casework_checklist_states = Table(
    "casework_checklist_states",
    metadata,
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("playbook_version_id", UUID(as_uuid=True), nullable=False),
    Column("checklist_item_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("note", Text, nullable=True),
    Column("updated_by", String(128), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("row_version", Integer, nullable=False, server_default=text("1")),
    PrimaryKeyConstraint(
        "matter_id",
        "playbook_version_id",
        "checklist_item_id",
        name="pk_casework_checklist_states",
    ),
    ForeignKeyConstraint(
        ["matter_id", "playbook_version_id"],
        [
            "casework_matters.matter_id",
            "casework_matters.assigned_playbook_version_id",
        ],
        name="fk_casework_checklist_states_matter_pin",
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        f"status IN ({_CHECKLIST_STATUSES})",
        name="ck_casework_checklist_states_status",
    ),
    CheckConstraint(
        "note IS NULL OR char_length(note) <= 512",
        name="ck_casework_checklist_states_note_length",
    ),
    CheckConstraint(
        "char_length(checklist_item_id) <= 64 AND char_length(btrim(checklist_item_id)) > 0",
        name="ck_casework_checklist_states_item_id",
    ),
    CheckConstraint(
        "row_version >= 1",
        name="ck_casework_checklist_states_row_version_positive",
    ),
    CheckConstraint(
        "char_length(btrim(updated_by)) > 0",
        name="ck_casework_checklist_states_updated_by_nonblank",
    ),
)

casework_checklist_states_history = Table(
    "casework_checklist_states_history",
    metadata,
    Column("history_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("playbook_version_id", UUID(as_uuid=True), nullable=False),
    Column("checklist_item_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("note", Text, nullable=True),
    Column("updated_by", String(128), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("row_version", Integer, nullable=False),
    Column("superseded_at", DateTime(timezone=True), nullable=False),
    Column("superseded_by", String(128), nullable=False),
    Column("superseded_by_playbook_version_id", UUID(as_uuid=True), nullable=False),
    Column("upgrade_correlation_id", UUID(as_uuid=True), nullable=False),
    PrimaryKeyConstraint(
        "history_id",
        name="pk_casework_checklist_states_history",
    ),
    ForeignKeyConstraint(
        ["matter_id"],
        ["casework_matters.matter_id"],
        name="fk_casework_checklist_states_history_matter_id",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["playbook_version_id"],
        ["playbook_versions.playbook_version_id"],
        name="fk_casework_checklist_states_history_version",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["superseded_by_playbook_version_id"],
        ["playbook_versions.playbook_version_id"],
        name="fk_casework_checklist_states_history_superseded_version",
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        f"status IN ({_CHECKLIST_STATUSES})",
        name="ck_casework_checklist_states_history_status",
    ),
    CheckConstraint(
        "note IS NULL OR char_length(note) <= 512",
        name="ck_casework_checklist_states_history_note_length",
    ),
    CheckConstraint(
        "char_length(checklist_item_id) <= 64 AND char_length(btrim(checklist_item_id)) > 0",
        name="ck_casework_checklist_states_history_item_id",
    ),
    CheckConstraint(
        "row_version >= 1",
        name="ck_casework_checklist_states_history_row_version",
    ),
    CheckConstraint(
        "char_length(btrim(updated_by)) > 0",
        name="ck_casework_checklist_states_history_updated_by_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(superseded_by)) > 0",
        name="ck_casework_checklist_states_history_superseded_by_nonblank",
    ),
)

PLAYBOOK_TABLES = (
    playbooks,
    playbook_versions,
    playbook_audit_events,
    casework_playbook_evaluations,
    casework_playbook_evaluation_candidates,
    casework_intake_answers,
    casework_intake_answers_history,
    casework_checklist_states,
    casework_checklist_states_history,
)

assert isinstance(metadata, MetaData)

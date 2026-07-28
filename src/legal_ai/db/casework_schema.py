"""SQLAlchemy Core tables for Phase 1 Generic Casework Core."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
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

casework_matters = Table(
    "casework_matters",
    metadata,
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("reference", String(32), nullable=False),
    Column("title", Text, nullable=False),
    Column("summary", Text, nullable=True),
    Column("status", String(64), nullable=False),
    Column("jurisdiction", String(16), nullable=False),
    Column("case_type", String(64), nullable=False),
    Column("risk_level", String(8), nullable=False),
    Column("action_authority_ceiling", String(8), nullable=False),
    Column("row_version", Integer, nullable=False, server_default=text("1")),
    Column("created_by", String(128), nullable=False),
    Column("updated_by", String(128), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column("closed_at", DateTime(timezone=True), nullable=True),
    PrimaryKeyConstraint("matter_id", name="pk_casework_matters"),
    UniqueConstraint("reference", name="uq_casework_matters_reference"),
    CheckConstraint(
        f"status IN ({_MATTER_STATUSES})",
        name="ck_casework_matters_status",
    ),
    CheckConstraint(
        f"jurisdiction IN ({_JURISDICTIONS})",
        name="ck_casework_matters_jurisdiction",
    ),
    CheckConstraint(
        f"case_type IN ({_CASE_TYPES})",
        name="ck_casework_matters_case_type",
    ),
    CheckConstraint(
        f"risk_level IN ({_RISK_LEVELS})",
        name="ck_casework_matters_risk_level",
    ),
    CheckConstraint(
        f"action_authority_ceiling IN ({_AUTHORITIES})",
        name="ck_casework_matters_authority_ceiling",
    ),
    CheckConstraint(
        "row_version >= 1",
        name="ck_casework_matters_row_version_positive",
    ),
    CheckConstraint(
        "char_length(btrim(title)) > 0",
        name="ck_casework_matters_title_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(created_by)) > 0",
        name="ck_casework_matters_created_by_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(updated_by)) > 0",
        name="ck_casework_matters_updated_by_nonblank",
    ),
)

casework_parties = Table(
    "casework_parties",
    metadata,
    Column("party_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("entity_type", String(32), nullable=False),
    Column("display_name", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    PrimaryKeyConstraint("party_id", name="pk_casework_parties"),
    ForeignKeyConstraint(
        ["matter_id"],
        ["casework_matters.matter_id"],
        name="fk_casework_parties_matter_id",
        ondelete="RESTRICT",
    ),
    UniqueConstraint(
        "matter_id",
        "party_id",
        name="uq_casework_parties_matter_party",
    ),
    CheckConstraint(
        f"entity_type IN ({_PARTY_ENTITY_TYPES})",
        name="ck_casework_parties_entity_type",
    ),
    CheckConstraint(
        "char_length(btrim(display_name)) > 0",
        name="ck_casework_parties_display_name_nonblank",
    ),
)

Index("ix_casework_parties_matter_id", casework_parties.c.matter_id)

casework_party_roles = Table(
    "casework_party_roles",
    metadata,
    Column("role_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("party_id", UUID(as_uuid=True), nullable=False),
    Column("role", String(32), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    PrimaryKeyConstraint("role_id", name="pk_casework_party_roles"),
    ForeignKeyConstraint(
        ["matter_id", "party_id"],
        ["casework_parties.matter_id", "casework_parties.party_id"],
        name="fk_casework_party_roles_party",
        ondelete="RESTRICT",
    ),
    UniqueConstraint(
        "matter_id",
        "party_id",
        "role",
        name="uq_casework_party_roles_matter_party_role",
    ),
    CheckConstraint(
        f"role IN ({_PARTY_ROLES})",
        name="ck_casework_party_roles_role",
    ),
)

casework_fact_items = Table(
    "casework_fact_items",
    metadata,
    Column("fact_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("statement", Text, nullable=False),
    Column("source_ref", Text, nullable=True),
    Column("source_channel", String(64), nullable=True),
    Column("verified_by", String(128), nullable=True),
    Column("verified_at", DateTime(timezone=True), nullable=True),
    Column("verification_method", String(64), nullable=True),
    Column("verification_source_ref", Text, nullable=True),
    Column("verification_note", Text, nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    PrimaryKeyConstraint("fact_id", name="pk_casework_fact_items"),
    ForeignKeyConstraint(
        ["matter_id"],
        ["casework_matters.matter_id"],
        name="fk_casework_fact_items_matter_id",
        ondelete="RESTRICT",
    ),
    CheckConstraint(f"kind IN ({_FACT_KINDS})", name="ck_casework_fact_items_kind"),
    CheckConstraint(
        f"status IN ({_FACT_STATUSES})",
        name="ck_casework_fact_items_status",
    ),
    CheckConstraint(
        "char_length(btrim(statement)) > 0",
        name="ck_casework_fact_items_statement_nonblank",
    ),
    CheckConstraint(
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
    CheckConstraint(
        f"verification_method IS NULL OR verification_method IN ({_VERIFICATION_METHODS})",
        name="ck_casework_fact_items_verification_method",
    ),
)

Index("ix_casework_fact_items_matter_id", casework_fact_items.c.matter_id)

casework_issues = Table(
    "casework_issues",
    metadata,
    Column("issue_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("issue_type", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("question_or_topic", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    PrimaryKeyConstraint("issue_id", name="pk_casework_issues"),
    ForeignKeyConstraint(
        ["matter_id"],
        ["casework_matters.matter_id"],
        name="fk_casework_issues_matter_id",
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        f"issue_type IN ({_ISSUE_TYPES})",
        name="ck_casework_issues_issue_type",
    ),
    CheckConstraint(
        f"status IN ({_ISSUE_STATUSES})",
        name="ck_casework_issues_status",
    ),
    CheckConstraint(
        "char_length(btrim(question_or_topic)) > 0",
        name="ck_casework_issues_topic_nonblank",
    ),
)

Index("ix_casework_issues_matter_id", casework_issues.c.matter_id)

casework_deadlines = Table(
    "casework_deadlines",
    metadata,
    Column("deadline_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("source_description", Text, nullable=False),
    Column("source_ref", Text, nullable=True),
    Column("jurisdiction", String(16), nullable=False),
    Column("confidence", String(16), nullable=False),
    Column("responsible_actor", String(128), nullable=False),
    Column("timezone", String(64), nullable=False),
    Column("precision", String(16), nullable=False),
    Column("due_date", Date, nullable=True),
    Column("due_at", DateTime(timezone=True), nullable=True),
    Column("status", String(16), nullable=False),
    Column(
        "human_confirmation_required",
        Boolean,
        nullable=False,
        server_default=text("true"),
    ),
    Column("confirmed_by", String(128), nullable=True),
    Column("confirmed_at", DateTime(timezone=True), nullable=True),
    Column("confirmation_method", String(64), nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    PrimaryKeyConstraint("deadline_id", name="pk_casework_deadlines"),
    ForeignKeyConstraint(
        ["matter_id"],
        ["casework_matters.matter_id"],
        name="fk_casework_deadlines_matter_id",
        ondelete="RESTRICT",
    ),
    UniqueConstraint(
        "matter_id",
        "deadline_id",
        name="uq_casework_deadlines_matter_deadline",
    ),
    CheckConstraint(
        f"jurisdiction IN ({_JURISDICTIONS})",
        name="ck_casework_deadlines_jurisdiction",
    ),
    CheckConstraint(
        f"confidence IN ({_DEADLINE_CONFIDENCES})",
        name="ck_casework_deadlines_confidence",
    ),
    CheckConstraint(
        f"precision IN ({_DEADLINE_PRECISIONS})",
        name="ck_casework_deadlines_precision",
    ),
    CheckConstraint(
        f"status IN ({_DEADLINE_STATUSES})",
        name="ck_casework_deadlines_status",
    ),
    CheckConstraint(
        "("
        "precision = 'DATE' AND due_date IS NOT NULL AND due_at IS NULL"
        ") OR ("
        "precision = 'DATETIME' AND due_at IS NOT NULL AND due_date IS NULL"
        ")",
        name="ck_casework_deadlines_precision_due",
    ),
    CheckConstraint(
        "("
        "confirmed_by IS NULL AND confirmed_at IS NULL AND confirmation_method IS NULL"
        ") OR ("
        "confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL "
        "AND confirmation_method IS NOT NULL "
        f"AND confirmation_method IN ({_CONFIRMATION_METHODS})"
        ")",
        name="ck_casework_deadlines_confirmation_fields",
    ),
    CheckConstraint(
        "char_length(btrim(source_description)) > 0",
        name="ck_casework_deadlines_source_description_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(timezone)) > 0",
        name="ck_casework_deadlines_timezone_nonblank",
    ),
)

Index("ix_casework_deadlines_matter_id", casework_deadlines.c.matter_id)

casework_tasks = Table(
    "casework_tasks",
    metadata,
    Column("task_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("title", Text, nullable=False),
    Column("status", String(16), nullable=False),
    Column("deadline_id", UUID(as_uuid=True), nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    PrimaryKeyConstraint("task_id", name="pk_casework_tasks"),
    ForeignKeyConstraint(
        ["matter_id"],
        ["casework_matters.matter_id"],
        name="fk_casework_tasks_matter_id",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["matter_id", "deadline_id"],
        ["casework_deadlines.matter_id", "casework_deadlines.deadline_id"],
        name="fk_casework_tasks_deadline",
        ondelete="RESTRICT",
    ),
    CheckConstraint(f"status IN ({_TASK_STATUSES})", name="ck_casework_tasks_status"),
    CheckConstraint(
        "char_length(btrim(title)) > 0",
        name="ck_casework_tasks_title_nonblank",
    ),
)

Index("ix_casework_tasks_matter_id", casework_tasks.c.matter_id)

casework_audit_events = Table(
    "casework_audit_events",
    metadata,
    Column("event_id", UUID(as_uuid=True), nullable=False),
    Column("matter_id", UUID(as_uuid=True), nullable=False),
    Column("actor", String(128), nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("entity_type", String(64), nullable=False),
    Column("entity_id", UUID(as_uuid=True), nullable=True),
    Column(
        "occurred_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column("correlation_id", UUID(as_uuid=True), nullable=True),
    Column("reason", Text, nullable=True),
    Column("source_channel", String(64), nullable=False),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    PrimaryKeyConstraint("event_id", name="pk_casework_audit_events"),
    ForeignKeyConstraint(
        ["matter_id"],
        ["casework_matters.matter_id"],
        name="fk_casework_audit_events_matter_id",
        ondelete="RESTRICT",
    ),
    CheckConstraint(
        "char_length(btrim(actor)) > 0",
        name="ck_casework_audit_events_actor_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(event_type)) > 0",
        name="ck_casework_audit_events_event_type_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(entity_type)) > 0",
        name="ck_casework_audit_events_entity_type_nonblank",
    ),
    CheckConstraint(
        "char_length(btrim(source_channel)) > 0",
        name="ck_casework_audit_events_source_channel_nonblank",
    ),
    CheckConstraint(
        "pg_column_size(metadata) <= 4096",
        name="ck_casework_audit_events_metadata_size",
    ),
)

Index(
    "ix_casework_audit_events_matter_occurred",
    casework_audit_events.c.matter_id,
    casework_audit_events.c.occurred_at,
)

CASEWORK_TABLES = (
    casework_matters,
    casework_parties,
    casework_party_roles,
    casework_fact_items,
    casework_issues,
    casework_deadlines,
    casework_tasks,
    casework_audit_events,
)

# Ensure metadata identity for typing consumers.
assert isinstance(metadata, MetaData)

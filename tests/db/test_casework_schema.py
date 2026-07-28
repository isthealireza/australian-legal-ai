from sqlalchemy import CheckConstraint, ForeignKeyConstraint

from legal_ai.db import (
    casework_audit_events,
    casework_deadlines,
    casework_fact_items,
    casework_matters,
    casework_parties,
    metadata,
)

_EXPECTED_CASEWORK_TABLES = {
    "casework_matters",
    "casework_parties",
    "casework_party_roles",
    "casework_fact_items",
    "casework_issues",
    "casework_deadlines",
    "casework_tasks",
    "casework_audit_events",
}


def test_metadata_contains_casework_tables() -> None:
    assert _EXPECTED_CASEWORK_TABLES <= set(metadata.tables)


def test_matters_declare_key_check_constraints() -> None:
    check_names = {
        constraint.name
        for constraint in casework_matters.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_casework_matters_status",
        "ck_casework_matters_jurisdiction",
        "ck_casework_matters_case_type",
        "ck_casework_matters_risk_level",
        "ck_casework_matters_authority_ceiling",
        "ck_casework_matters_row_version_positive",
        "ck_casework_matters_title_nonblank",
        "ck_casework_matters_created_by_nonblank",
        "ck_casework_matters_updated_by_nonblank",
    } <= check_names


def test_fact_items_declare_key_check_constraints() -> None:
    check_names = {
        constraint.name
        for constraint in casework_fact_items.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_casework_fact_items_kind",
        "ck_casework_fact_items_status",
        "ck_casework_fact_items_statement_nonblank",
        "ck_casework_fact_items_verification_fields",
        "ck_casework_fact_items_verification_method",
    } <= check_names


def test_deadlines_declare_key_check_constraints() -> None:
    check_names = {
        constraint.name
        for constraint in casework_deadlines.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_casework_deadlines_jurisdiction",
        "ck_casework_deadlines_confidence",
        "ck_casework_deadlines_precision",
        "ck_casework_deadlines_status",
        "ck_casework_deadlines_precision_due",
        "ck_casework_deadlines_confirmation_fields",
        "ck_casework_deadlines_source_description_nonblank",
        "ck_casework_deadlines_timezone_nonblank",
    } <= check_names


def test_audit_events_declare_key_check_constraints() -> None:
    check_names = {
        constraint.name
        for constraint in casework_audit_events.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_casework_audit_events_actor_nonblank",
        "ck_casework_audit_events_event_type_nonblank",
        "ck_casework_audit_events_entity_type_nonblank",
        "ck_casework_audit_events_source_channel_nonblank",
        "ck_casework_audit_events_metadata_size",
    } <= check_names


def test_parties_matter_foreign_key_is_restrict() -> None:
    foreign_keys = [
        constraint
        for constraint in casework_parties.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    matter_fks = [fk for fk in foreign_keys if fk.name == "fk_casework_parties_matter_id"]
    assert len(matter_fks) == 1
    assert matter_fks[0].ondelete == "RESTRICT"

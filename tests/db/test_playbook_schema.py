from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from legal_ai.db import (
    casework_checklist_states,
    casework_intake_answers,
    casework_matters,
    casework_playbook_evaluation_candidates,
    casework_playbook_evaluations,
    metadata,
    playbook_audit_events,
    playbook_versions,
    playbooks,
)

_EXPECTED_PLAYBOOK_TABLES = {
    "playbooks",
    "playbook_versions",
    "playbook_audit_events",
    "casework_playbook_evaluations",
    "casework_playbook_evaluation_candidates",
    "casework_intake_answers",
    "casework_intake_answers_history",
    "casework_checklist_states",
    "casework_checklist_states_history",
}


def test_metadata_contains_playbook_tables() -> None:
    assert _EXPECTED_PLAYBOOK_TABLES <= set(metadata.tables)


def test_matters_declare_playbook_pin_columns_and_constraints() -> None:
    assert {
        "assigned_playbook_version_id",
        "playbook_assigned_at",
        "playbook_assigned_by",
    } <= set(casework_matters.c.keys())

    unique_names = {
        constraint.name
        for constraint in casework_matters.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert "uq_casework_matters_matter_pin" in unique_names

    check_sql = next(
        constraint.sqltext.text
        for constraint in casework_matters.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_casework_matters_case_type"
    )
    assert "MOTOR_VEHICLE_PROPERTY_DAMAGE" in check_sql

    foreign_keys = [
        constraint
        for constraint in casework_matters.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    pin_fks = [
        fk for fk in foreign_keys if fk.name == "fk_casework_matters_assigned_playbook_version_id"
    ]
    assert len(pin_fks) == 1
    assert pin_fks[0].ondelete == "RESTRICT"


def test_playbook_versions_declare_key_check_constraints() -> None:
    check_names = {
        constraint.name
        for constraint in playbook_versions.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_playbook_versions_status",
        "ck_playbook_versions_version_positive",
        "ck_playbook_versions_row_version_positive",
        "ck_playbook_versions_definition_size",
        "ck_playbook_versions_content_sha256",
    } <= check_names
    assert playbooks.primary_key.columns.keys() == ["playbook_key"]


def test_evaluation_candidates_declare_primary_and_unique_keys() -> None:
    assert casework_playbook_evaluation_candidates.primary_key.columns.keys() == [
        "evaluation_id",
        "playbook_version_id",
    ]
    unique_names = {
        constraint.name
        for constraint in casework_playbook_evaluation_candidates.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert "uq_casework_playbook_evaluation_candidates_order" in unique_names


def test_intake_and_checklist_use_matter_pin_foreign_keys() -> None:
    for table, expected_name in (
        (casework_intake_answers, "fk_casework_intake_answers_matter_pin"),
        (casework_checklist_states, "fk_casework_checklist_states_matter_pin"),
    ):
        foreign_keys = [
            constraint
            for constraint in table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
        ]
        pin_fks = [fk for fk in foreign_keys if fk.name == expected_name]
        assert len(pin_fks) == 1
        assert pin_fks[0].ondelete == "RESTRICT"


def test_playbook_audit_and_evaluations_are_present() -> None:
    assert playbook_audit_events.name == "playbook_audit_events"
    assert casework_playbook_evaluations.name == "casework_playbook_evaluations"

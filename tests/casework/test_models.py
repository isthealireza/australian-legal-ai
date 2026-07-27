"""Unit tests for casework Pydantic commands and audit metadata rules."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from legal_ai.casework.models import (
    AUDIT_METADATA_ALLOWLIST,
    AddDeadlineCommand,
    AddFactCommand,
    CreateMatterCommand,
    ReopenMatterCommand,
    UpdateFactStatusCommand,
    validate_audit_metadata,
)
from legal_ai.casework.types import (
    ActionAuthorityLevel,
    CaseType,
    DeadlineConfidence,
    DeadlinePrecision,
    FactKind,
    FactStatus,
    Jurisdiction,
    MatterStatus,
    RiskLevel,
    VerificationMethod,
)


def _create_matter_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "title": "Test matter",
        "jurisdiction": Jurisdiction.AU_WA,
        "case_type": CaseType.UNASSIGNED,
        "risk_level": RiskLevel.R1,
        "action_authority_ceiling": ActionAuthorityLevel.L1,
        "actor": "operator.one",
        "source_channel": "unit-test",
    }
    data.update(overrides)
    return data


def test_create_matter_command_accepts_phase1_ceiling() -> None:
    command = CreateMatterCommand.model_validate(_create_matter_data())
    assert command.action_authority_ceiling is ActionAuthorityLevel.L1
    assert command.jurisdiction is Jurisdiction.AU_WA


def test_create_matter_rejects_l3_ceiling() -> None:
    with pytest.raises(ValidationError):
        CreateMatterCommand.model_validate(
            _create_matter_data(action_authority_ceiling=ActionAuthorityLevel.L3)
        )


def test_create_matter_rejects_blank_title() -> None:
    with pytest.raises(ValidationError):
        CreateMatterCommand.model_validate(_create_matter_data(title="   "))


def test_create_matter_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CreateMatterCommand.model_validate(_create_matter_data(playbook_id="x"))


@pytest.mark.parametrize("jurisdiction", list(Jurisdiction))
def test_all_jurisdictions_accepted(jurisdiction: Jurisdiction) -> None:
    command = CreateMatterCommand.model_validate(_create_matter_data(jurisdiction=jurisdiction))
    assert command.jurisdiction is jurisdiction


def test_add_fact_rejects_verified_on_create() -> None:
    with pytest.raises(ValidationError):
        AddFactCommand.model_validate(
            {
                "matter_id": uuid4(),
                "kind": FactKind.OBSERVED,
                "statement": "seen",
                "status": FactStatus.VERIFIED,
                "actor": "op",
                "source_channel": "unit",
            }
        )


def test_update_fact_verified_operator_attestation_allows_null_source_ref() -> None:
    command = UpdateFactStatusCommand.model_validate(
        {
            "matter_id": uuid4(),
            "fact_id": uuid4(),
            "status": FactStatus.VERIFIED,
            "actor": "op",
            "source_channel": "unit",
            "verified_by": "op",
            "verified_at": datetime(2026, 7, 28, tzinfo=UTC),
            "verification_method": VerificationMethod.OPERATOR_ATTESTATION,
            "verification_note": "attested",
        }
    )
    assert command.verification_source_ref is None


def test_update_fact_verified_document_review_requires_source_ref() -> None:
    with pytest.raises(ValidationError):
        UpdateFactStatusCommand.model_validate(
            {
                "matter_id": uuid4(),
                "fact_id": uuid4(),
                "status": FactStatus.VERIFIED,
                "actor": "op",
                "source_channel": "unit",
                "verified_by": "op",
                "verified_at": datetime(2026, 7, 28, tzinfo=UTC),
                "verification_method": VerificationMethod.DOCUMENT_REVIEW,
                "verification_note": "reviewed",
            }
        )


def test_update_fact_non_verified_rejects_verification_fields() -> None:
    with pytest.raises(ValidationError):
        UpdateFactStatusCommand.model_validate(
            {
                "matter_id": uuid4(),
                "fact_id": uuid4(),
                "status": FactStatus.ASSERTED,
                "actor": "op",
                "source_channel": "unit",
                "verified_by": "op",
            }
        )


def test_deadline_date_precision_xor() -> None:
    AddDeadlineCommand.model_validate(
        {
            "matter_id": uuid4(),
            "source_description": "court listing",
            "jurisdiction": Jurisdiction.AU_WA,
            "confidence": DeadlineConfidence.HIGH,
            "responsible_actor": "op",
            "timezone": "Australia/Perth",
            "precision": DeadlinePrecision.DATE,
            "due_date": date(2026, 8, 1),
            "actor": "op",
            "source_channel": "unit",
        }
    )
    with pytest.raises(ValidationError):
        AddDeadlineCommand.model_validate(
            {
                "matter_id": uuid4(),
                "source_description": "court listing",
                "jurisdiction": Jurisdiction.AU_WA,
                "confidence": DeadlineConfidence.HIGH,
                "responsible_actor": "op",
                "timezone": "Australia/Perth",
                "precision": DeadlinePrecision.DATE,
                "due_date": date(2026, 8, 1),
                "due_at": datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
                "actor": "op",
                "source_channel": "unit",
            }
        )


def test_deadline_rejects_invalid_timezone() -> None:
    with pytest.raises(ValidationError):
        AddDeadlineCommand.model_validate(
            {
                "matter_id": uuid4(),
                "source_description": "court listing",
                "jurisdiction": Jurisdiction.AU_WA,
                "confidence": DeadlineConfidence.HIGH,
                "responsible_actor": "op",
                "timezone": "Not/A_Zone",
                "precision": DeadlinePrecision.DATE,
                "due_date": date(2026, 8, 1),
                "actor": "op",
                "source_channel": "unit",
            }
        )


def test_reopen_requires_nonempty_reason_and_valid_target() -> None:
    with pytest.raises(ValidationError):
        ReopenMatterCommand.model_validate(
            {
                "matter_id": uuid4(),
                "row_version": 1,
                "target_status": MatterStatus.ACTIVE,
                "actor": "op",
                "source_channel": "unit",
                "reason": "   ",
            }
        )
    with pytest.raises(ValidationError):
        ReopenMatterCommand.model_validate(
            {
                "matter_id": uuid4(),
                "row_version": 1,
                "target_status": MatterStatus.WAITING,
                "actor": "op",
                "source_channel": "unit",
                "reason": "reopen please",
            }
        )


def test_audit_metadata_allowlist_and_size() -> None:
    validate_audit_metadata({"command_type": "CreateMatter"})
    with pytest.raises(ValueError, match="allowlisted"):
        validate_audit_metadata({"payload": "secret"})
    huge = {"command_type": "x" * 5000}
    assert "command_type" in AUDIT_METADATA_ALLOWLIST
    with pytest.raises(ValueError, match="4 KiB"):
        validate_audit_metadata(huge)

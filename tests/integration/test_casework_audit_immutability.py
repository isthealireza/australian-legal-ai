"""PostgreSQL-enforced audit immutability integration tests."""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from legal_ai.casework.models import CreateMatterCommand
from legal_ai.casework.repository import CaseworkRepository
from legal_ai.casework.service import CaseworkService
from legal_ai.casework.types import (
    ActionAuthorityLevel,
    CaseType,
    Jurisdiction,
    RiskLevel,
)

pytestmark = pytest.mark.integration


def test_direct_sql_audit_update_rejected(migrated_engine: Engine) -> None:
    service = CaseworkService(CaseworkRepository(migrated_engine))
    matter = service.create_matter(
        CreateMatterCommand(
            title="Audit immutability",
            summary=None,
            jurisdiction=Jurisdiction.AU_CTH,
            case_type=CaseType.UNASSIGNED,
            risk_level=RiskLevel.R0,
            action_authority_ceiling=ActionAuthorityLevel.L1,
            actor="tester",
            source_channel="test",
            correlation_id=None,
        )
    )
    with migrated_engine.connect() as connection:
        event_id = connection.execute(
            text("SELECT event_id FROM casework_audit_events WHERE matter_id = :matter_id LIMIT 1"),
            {"matter_id": matter.matter_id},
        ).scalar_one()
        connection.commit()

    with pytest.raises(DBAPIError, match="immutable"):
        with migrated_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE casework_audit_events SET reason = 'tamper' WHERE event_id = :event_id"
                ),
                {"event_id": event_id},
            )


def test_direct_sql_audit_delete_rejected(migrated_engine: Engine) -> None:
    service = CaseworkService(CaseworkRepository(migrated_engine))
    matter = service.create_matter(
        CreateMatterCommand(
            title="Audit delete blocked",
            summary=None,
            jurisdiction=Jurisdiction.AU_NSW,
            case_type=CaseType.UNASSIGNED,
            risk_level=RiskLevel.R1,
            action_authority_ceiling=ActionAuthorityLevel.L1,
            actor="tester",
            source_channel="test",
            correlation_id=None,
        )
    )
    with migrated_engine.connect() as connection:
        event_id = connection.execute(
            text("SELECT event_id FROM casework_audit_events WHERE matter_id = :matter_id LIMIT 1"),
            {"matter_id": matter.matter_id},
        ).scalar_one()
        connection.commit()

    with pytest.raises(DBAPIError, match="immutable"):
        with migrated_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM casework_audit_events WHERE event_id = :event_id"),
                {"event_id": event_id},
            )


def test_repository_has_no_audit_update_or_delete_api() -> None:
    methods = dir(CaseworkRepository)
    assert "update_audit_event" not in methods
    assert "delete_audit_event" not in methods
    assert "append_audit_event" in methods

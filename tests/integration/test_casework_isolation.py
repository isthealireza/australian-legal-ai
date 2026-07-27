"""Adversarial matter-isolation integration tests."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from legal_ai.casework.errors import CrossMatterViolationError, NotFoundError
from legal_ai.casework.models import (
    AddDeadlineCommand,
    AddPartyCommand,
    AssignRoleCommand,
    CreateMatterCommand,
)
from legal_ai.casework.repository import CaseworkRepository
from legal_ai.casework.service import CaseworkService
from legal_ai.casework.types import (
    ActionAuthorityLevel,
    CaseType,
    DeadlineConfidence,
    DeadlinePrecision,
    Jurisdiction,
    PartyEntityType,
    PartyRole,
    RiskLevel,
)

pytestmark = pytest.mark.integration


def _service(engine: Engine) -> CaseworkService:
    return CaseworkService(CaseworkRepository(engine))


def _create_matter(service: CaseworkService, *, title: str) -> object:
    return service.create_matter(
        CreateMatterCommand(
            title=title,
            summary=None,
            jurisdiction=Jurisdiction.AU_WA,
            case_type=CaseType.UNASSIGNED,
            risk_level=RiskLevel.R0,
            action_authority_ceiling=ActionAuthorityLevel.L1,
            actor="tester",
            source_channel="test",
            correlation_id=None,
        )
    )


def test_cannot_read_party_from_other_matter(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)
    matter_a = _create_matter(service, title="Matter A")
    matter_b = _create_matter(service, title="Matter B")
    party = service.add_party(
        AddPartyCommand(
            matter_id=matter_a.matter_id,
            entity_type=PartyEntityType.NATURAL_PERSON,
            display_name="Alice",
            actor="tester",
            source_channel="test",
            correlation_id=None,
        )
    )
    with pytest.raises((NotFoundError, CrossMatterViolationError)):
        service.assign_role(
            AssignRoleCommand(
                matter_id=matter_b.matter_id,
                party_id=party.party_id,
                role=PartyRole.PRIMARY_SUBJECT,
                actor="tester",
                source_channel="test",
                correlation_id=None,
            )
        )


def test_cannot_attach_deadline_cross_matter_via_sql(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)
    matter_a = _create_matter(service, title="Matter A")
    matter_b = _create_matter(service, title="Matter B")
    deadline = service.add_deadline(
        AddDeadlineCommand(
            matter_id=matter_a.matter_id,
            source_description="Manual insurer follow-up",
            source_ref=None,
            jurisdiction=Jurisdiction.AU_WA,
            confidence=DeadlineConfidence.MEDIUM,
            responsible_actor="tester",
            timezone="Australia/Perth",
            precision=DeadlinePrecision.DATE,
            due_date=date(2026, 8, 1),
            due_at=None,
            human_confirmation_required=True,
            actor="tester",
            source_channel="test",
            correlation_id=None,
        )
    )
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO casework_tasks (
                        task_id, matter_id, title, status, deadline_id
                    ) VALUES (
                        :task_id, :matter_id, 'x', 'OPEN', :deadline_id
                    )
                    """
                ),
                {
                    "task_id": uuid4(),
                    "matter_id": matter_b.matter_id,
                    "deadline_id": deadline.deadline_id,
                },
            )


def test_audit_events_not_readable_as_other_matter_mutation_target(
    migrated_engine: Engine,
) -> None:
    service = _service(migrated_engine)
    matter_a = _create_matter(service, title="Matter A")
    matter_b = _create_matter(service, title="Matter B")
    repo = CaseworkRepository(migrated_engine)
    with repo.transaction() as connection:
        events_a = repo.list_audit_events(connection, matter_a.matter_id)
        events_b = repo.list_audit_events(connection, matter_b.matter_id)
    assert all(event.matter_id == matter_a.matter_id for event in events_a)
    assert all(event.matter_id == matter_b.matter_id for event in events_b)
    assert {event.event_id for event in events_a}.isdisjoint({event.event_id for event in events_b})

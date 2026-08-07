from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, func, insert, select, update

from legal_ai.db import (
    casework_audit_events,
    casework_checklist_states,
    casework_evidence_checklist_links,
    casework_evidence_records,
    casework_matters,
    playbook_versions,
    playbooks,
)
from legal_ai.evidence.errors import EvidenceAuditWriteFailed, MalformedSignature
from legal_ai.evidence.models import (
    LinkEvidenceChecklistCommand,
    RegisterDerivedEvidenceCommand,
    ReviewEvidenceCommand,
    UploadEvidenceCommand,
)
from legal_ai.evidence.repository import EvidenceRepository
from legal_ai.evidence.service import EvidenceService
from legal_ai.evidence.types import EvidenceReviewStatus, EvidenceRole
from legal_ai.provenance import LocalArtifactStore


def create_matter(engine: Engine, *, status: str = "ACTIVE", authority: str = "L1") -> UUID:
    matter_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            insert(casework_matters).values(
                matter_id=matter_id,
                reference=f"MAT-{matter_id.hex[:12]}",
                title="Synthetic matter",
                status=status,
                jurisdiction="AU-WA",
                case_type="UNSUPPORTED",
                risk_level="R0",
                action_authority_ceiling=authority,
                created_by="tester",
                updated_by="tester",
            )
        )
    return matter_id


def service(engine: Engine, root: Path) -> EvidenceService:
    return EvidenceService(EvidenceRepository(engine), LocalArtifactStore(root))


def upload_command(
    matter_id: UUID, *, name: str = "note.txt", size: int = 5
) -> UploadEvidenceCommand:
    return UploadEvidenceCommand(
        matter_id=matter_id,
        caller_filename=name,
        declared_media_type="text/plain",
        expected_byte_size=size,
        actor="tester",
        source_channel="integration",
    )


def test_original_registration_duplicate_reuse_and_review(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    first = vault.upload(upload_command(matter_id), [b"hello"])
    duplicate = vault.upload(upload_command(matter_id), [b"hello"])
    assert duplicate.evidence_id == first.evidence_id
    reviewed = vault.review(
        ReviewEvidenceCommand(
            matter_id=matter_id,
            evidence_id=first.evidence_id,
            expected_row_version=1,
            target_status=EvidenceReviewStatus.REVIEW_ACCEPTED,
            reviewer="reviewer",
            reviewed_at=datetime.now(UTC),
            reason="synthetic review",
            source_channel="integration",
        )
    )
    assert reviewed.review_status is EvidenceReviewStatus.REVIEW_ACCEPTED
    assert reviewed.row_version == 2
    with migrated_engine.connect() as connection:
        events = (
            connection.execute(
                select(casework_audit_events.c.event_type).where(
                    casework_audit_events.c.matter_id == matter_id
                )
            )
            .scalars()
            .all()
        )
    assert "EVIDENCE_REGISTERED" in events
    assert "EVIDENCE_DUPLICATE_REUSED" in events
    assert "EVIDENCE_REVIEW_RECORDED" in events


def test_derived_registration_records_immediate_source(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    source = vault.upload(upload_command(matter_id), [b"hello"])
    derived = vault.register_derived(
        RegisterDerivedEvidenceCommand(
            matter_id=matter_id,
            source_evidence_id=source.evidence_id,
            caller_filename="derived.txt",
            declared_media_type="text/plain",
            expected_byte_size=7,
            actor="tester",
            source_channel="integration",
            operation_code="NORMALIZE",
            operation_version="1",
            processor_version="runtime-1",
            deterministic=True,
        ),
        [b"derived"],
    )
    assert derived.evidence_role is EvidenceRole.DERIVED
    ancestry = vault.ancestry(
        __import__(
            "legal_ai.evidence.models", fromlist=["ReadEvidenceCommand"]
        ).ReadEvidenceCommand(
            matter_id=matter_id,
            evidence_id=derived.evidence_id,
            actor="tester",
            source_channel="integration",
        )
    )
    assert [item.source_evidence_id for item in ancestry] == [source.evidence_id]


def test_closed_denial_is_durable_and_has_no_business_mutation(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine, status="CLOSED")
    vault = service(migrated_engine, tmp_path)
    from legal_ai.evidence.errors import ClosedMatterEvidenceWriteDenied

    with pytest.raises(ClosedMatterEvidenceWriteDenied):
        vault.upload(upload_command(matter_id), [b"hello"])
    with migrated_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(casework_evidence_records)) == 0
        denial = (
            connection.execute(
                select(casework_audit_events).where(
                    casework_audit_events.c.matter_id == matter_id,
                    casework_audit_events.c.event_type == "ACTION_DENIED",
                )
            )
            .mappings()
            .one()
        )
    assert denial["actor"] == "tester"
    assert denial["metadata"]["reason_code"] == "CLOSED_MATTER"


def test_rejected_signature_is_audited_without_business_state(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    command = UploadEvidenceCommand(
        matter_id=matter_id,
        caller_filename="bad.png",
        declared_media_type="image/png",
        expected_byte_size=3,
        actor="tester",
        source_channel="integration",
    )
    with pytest.raises(MalformedSignature):
        vault.upload(command, [b"bad"])
    with migrated_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(casework_evidence_records)) == 0
        event = (
            connection.execute(
                select(casework_audit_events).where(
                    casework_audit_events.c.matter_id == matter_id,
                    casework_audit_events.c.event_type == "EVIDENCE_UPLOAD_REJECTED",
                )
            )
            .mappings()
            .one()
        )
    assert event["metadata"]["reason_code"] == "SIGNATURE_MALFORMED"


def test_audit_failure_rolls_back_registration_but_leaves_verified_blob(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    repo = EvidenceRepository(migrated_engine)
    vault = EvidenceService(repo, LocalArtifactStore(tmp_path))

    def fail_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    repo.casework.append_audit_event = fail_audit  # type: ignore[assignment]
    with pytest.raises(EvidenceAuditWriteFailed):
        vault.upload(upload_command(matter_id), [b"hello"])
    with migrated_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(casework_evidence_records)) == 0
    assert any(path.suffix == ".blob" for path in tmp_path.rglob("*.blob"))


def test_denial_audit_failure_raises_typed_failure(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine, status="CLOSED")
    repo = EvidenceRepository(migrated_engine)
    vault = EvidenceService(repo, LocalArtifactStore(tmp_path))

    def fail_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    repo.casework.append_audit_event = fail_audit  # type: ignore[assignment]
    with pytest.raises(EvidenceAuditWriteFailed):
        vault.upload(upload_command(matter_id), [b"hello"])
    with migrated_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(casework_evidence_records)) == 0


def test_concurrent_duplicate_upload_reuses_one_matter_record(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)

    def perform_upload(_: int) -> UUID:
        return (
            service(migrated_engine, tmp_path)
            .upload(upload_command(matter_id), [b"hello"])
            .evidence_id
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        evidence_ids = list(executor.map(perform_upload, range(2)))
    assert evidence_ids[0] == evidence_ids[1]
    with migrated_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(casework_evidence_records)) == 1


# --- Terminal review mutation audit tests ---


def test_accepted_to_rejected_is_denied(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    record = vault.upload(upload_command(matter_id), [b"hello"])
    vault.review(
        ReviewEvidenceCommand(
            matter_id=matter_id,
            evidence_id=record.evidence_id,
            expected_row_version=1,
            target_status=EvidenceReviewStatus.REVIEW_ACCEPTED,
            reviewer="r",
            reviewed_at=datetime.now(UTC),
            reason="ok",
            source_channel="int",
        )
    )
    from legal_ai.evidence.errors import TerminalReviewMutationDenied

    with pytest.raises(TerminalReviewMutationDenied):
        vault.review(
            ReviewEvidenceCommand(
                matter_id=matter_id,
                evidence_id=record.evidence_id,
                expected_row_version=2,
                target_status=EvidenceReviewStatus.REVIEW_REJECTED,
                reviewer="r",
                reviewed_at=datetime.now(UTC),
                reason="no",
                source_channel="int",
            )
        )
    with migrated_engine.connect() as connection:
        denial = (
            connection.execute(
                select(casework_audit_events).where(
                    casework_audit_events.c.matter_id == matter_id,
                    casework_audit_events.c.event_type == "ACTION_DENIED",
                )
            )
            .mappings()
            .one()
        )
    assert denial["metadata"]["reason_code"] == "TERMINAL_REVIEW_MUTATION"


def test_rejected_to_accepted_is_denied(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    record = vault.upload(upload_command(matter_id), [b"hello"])
    vault.review(
        ReviewEvidenceCommand(
            matter_id=matter_id,
            evidence_id=record.evidence_id,
            expected_row_version=1,
            target_status=EvidenceReviewStatus.REVIEW_REJECTED,
            reviewer="r",
            reviewed_at=datetime.now(UTC),
            reason="no",
            source_channel="int",
        )
    )
    from legal_ai.evidence.errors import TerminalReviewMutationDenied

    with pytest.raises(TerminalReviewMutationDenied):
        vault.review(
            ReviewEvidenceCommand(
                matter_id=matter_id,
                evidence_id=record.evidence_id,
                expected_row_version=2,
                target_status=EvidenceReviewStatus.REVIEW_ACCEPTED,
                reviewer="r",
                reviewed_at=datetime.now(UTC),
                reason="ok",
                source_channel="int",
            )
        )


def test_terminal_to_uploded_is_denied(migrated_engine: Engine, tmp_path: Path) -> None:
    """UPLOADED is rejected by ReviewEvidenceCommand Pydantic validation."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ReviewEvidenceCommand(
            matter_id=uuid4(),
            evidence_id=uuid4(),
            expected_row_version=1,
            target_status=EvidenceReviewStatus.UPLOADED,
            reviewer="r",
            reviewed_at=datetime.now(UTC),
            reason="revert",
            source_channel="int",
        )


def test_terminal_review_leaves_no_business_mutation(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    record = vault.upload(upload_command(matter_id), [b"hello"])
    vault.review(
        ReviewEvidenceCommand(
            matter_id=matter_id,
            evidence_id=record.evidence_id,
            expected_row_version=1,
            target_status=EvidenceReviewStatus.REVIEW_ACCEPTED,
            reviewer="r",
            reviewed_at=datetime.now(UTC),
            reason="ok",
            source_channel="int",
        )
    )
    from legal_ai.evidence.errors import TerminalReviewMutationDenied

    with pytest.raises(TerminalReviewMutationDenied):
        vault.review(
            ReviewEvidenceCommand(
                matter_id=matter_id,
                evidence_id=record.evidence_id,
                expected_row_version=2,
                target_status=EvidenceReviewStatus.REVIEW_REJECTED,
                reviewer="r",
                reviewed_at=datetime.now(UTC),
                reason="no",
                source_channel="int",
            )
        )
    with migrated_engine.connect() as connection:
        refreshed = (
            connection.execute(
                select(casework_evidence_records).where(
                    casework_evidence_records.c.evidence_id == record.evidence_id
                )
            )
            .mappings()
            .one()
        )
    assert refreshed["review_status"] == "REVIEW_ACCEPTED"
    assert refreshed["row_version"] == 2


def test_stale_row_version_is_not_terminal_audit(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    record = vault.upload(upload_command(matter_id), [b"hello"])
    from legal_ai.evidence.errors import InvalidReviewTransition

    with pytest.raises(InvalidReviewTransition):
        vault.review(
            ReviewEvidenceCommand(
                matter_id=matter_id,
                evidence_id=record.evidence_id,
                expected_row_version=99,
                target_status=EvidenceReviewStatus.REVIEW_ACCEPTED,
                reviewer="r",
                reviewed_at=datetime.now(UTC),
                reason="ok",
                source_channel="int",
            )
        )
    with migrated_engine.connect() as connection:
        events = (
            connection.execute(
                select(casework_audit_events.c.event_type).where(
                    casework_audit_events.c.matter_id == matter_id
                )
            )
            .scalars()
            .all()
        )
    assert "ACTION_DENIED" not in events


def test_denial_audit_failure_on_terminal_mutation(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    repo = EvidenceRepository(migrated_engine)
    vault = EvidenceService(repo, LocalArtifactStore(tmp_path))
    record = vault.upload(upload_command(matter_id), [b"hello"])
    vault.review(
        ReviewEvidenceCommand(
            matter_id=matter_id,
            evidence_id=record.evidence_id,
            expected_row_version=1,
            target_status=EvidenceReviewStatus.REVIEW_ACCEPTED,
            reviewer="r",
            reviewed_at=datetime.now(UTC),
            reason="ok",
            source_channel="int",
        )
    )
    from legal_ai.evidence.errors import EvidenceAuditWriteFailed

    def fail_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    repo.casework.append_audit_event = fail_audit  # type: ignore[assignment]
    with pytest.raises(EvidenceAuditWriteFailed):
        vault.review(
            ReviewEvidenceCommand(
                matter_id=matter_id,
                evidence_id=record.evidence_id,
                expected_row_version=2,
                target_status=EvidenceReviewStatus.REVIEW_REJECTED,
                reviewer="r",
                reviewed_at=datetime.now(UTC),
                reason="no",
                source_channel="int",
            )
        )
    with migrated_engine.connect() as connection:
        cols = (casework_evidence_records.c.review_status, casework_evidence_records.c.row_version)
        refreshed = connection.execute(
            select(*cols).where(casework_evidence_records.c.evidence_id == record.evidence_id)
        ).one()
    assert refreshed.review_status == "REVIEW_ACCEPTED"


# --- Derivation denial command type tests ---


def test_derivation_denial_has_correct_command_type(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    first_matter, second_matter = create_matter(migrated_engine), create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    source = vault.upload(upload_command(first_matter), [b"hello"])
    from legal_ai.evidence.errors import CrossMatterEvidenceDenied

    cmd = RegisterDerivedEvidenceCommand(
        matter_id=second_matter,
        source_evidence_id=source.evidence_id,
        caller_filename="derived.txt",
        declared_media_type="text/plain",
        expected_byte_size=7,
        actor="tester",
        source_channel="int",
        operation_code="NORM",
        operation_version="1",
        processor_version="r1",
        deterministic=True,
    )
    with pytest.raises(CrossMatterEvidenceDenied):
        vault.register_derived(cmd, [b"derived"])
    with migrated_engine.connect() as connection:
        denial = (
            connection.execute(
                select(casework_audit_events).where(
                    casework_audit_events.c.matter_id == second_matter,
                    casework_audit_events.c.event_type == "ACTION_DENIED",
                )
            )
            .mappings()
            .one()
        )
    assert denial["metadata"]["command_type"] == "DERIVE"


def test_uplod_denial_has_correct_command_type(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine, status="CLOSED")
    vault = service(migrated_engine, tmp_path)
    from legal_ai.evidence.errors import ClosedMatterEvidenceWriteDenied

    with pytest.raises(ClosedMatterEvidenceWriteDenied):
        vault.upload(upload_command(matter_id), [b"hello"])
    with migrated_engine.connect() as connection:
        denial = (
            connection.execute(
                select(casework_audit_events).where(
                    casework_audit_events.c.matter_id == matter_id,
                    casework_audit_events.c.event_type == "ACTION_DENIED",
                )
            )
            .mappings()
            .one()
        )
    assert denial["metadata"]["command_type"] == "UPLOAD"


def test_review_denial_has_correct_command_type(migrated_engine: Engine, tmp_path: Path) -> None:
    first_matter, second_matter = create_matter(migrated_engine), create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    ev = vault.upload(upload_command(first_matter), [b"hello"])
    from legal_ai.evidence.errors import CrossMatterEvidenceDenied

    with pytest.raises(CrossMatterEvidenceDenied):
        vault.review(
            ReviewEvidenceCommand(
                matter_id=second_matter,
                evidence_id=ev.evidence_id,
                expected_row_version=1,
                target_status=EvidenceReviewStatus.REVIEW_ACCEPTED,
                reviewer="r",
                reviewed_at=datetime.now(UTC),
                reason="ok",
                source_channel="int",
            )
        )
    with migrated_engine.connect() as connection:
        denial = (
            connection.execute(
                select(casework_audit_events).where(
                    casework_audit_events.c.matter_id == second_matter,
                    casework_audit_events.c.event_type == "ACTION_DENIED",
                )
            )
            .mappings()
            .one()
        )
    assert denial["metadata"]["command_type"] == "REVIEW"


def test_checklist_link_denial_has_correct_command_type(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    first_matter, second_matter = create_matter(migrated_engine), create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    ev = vault.upload(upload_command(first_matter), [b"hello"])
    from legal_ai.evidence.errors import CrossMatterEvidenceDenied

    with pytest.raises(CrossMatterEvidenceDenied):
        vault.link_checklist(
            LinkEvidenceChecklistCommand(
                matter_id=second_matter,
                evidence_id=ev.evidence_id,
                checklist_item_id="x",
                actor="t",
                linked_at=datetime.now(UTC),
                source_channel="int",
            )
        )
    with migrated_engine.connect() as connection:
        denial = (
            connection.execute(
                select(casework_audit_events).where(
                    casework_audit_events.c.matter_id == second_matter,
                    casework_audit_events.c.event_type == "ACTION_DENIED",
                )
            )
            .mappings()
            .one()
        )
    assert denial["metadata"]["command_type"] == "CHECKLIST_LINK"


# --- Checklist link reuse and conflict tests ---


def _setup_checklist_playbook(engine: Engine, matter_id: UUID) -> UUID:
    version_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            insert(playbooks).values(
                playbook_key="chk-test",
                display_name="Checklist test",
                created_by="tester",
            )
        )
        connection.execute(
            insert(playbook_versions).values(
                playbook_version_id=version_id,
                playbook_key="chk-test",
                version=1,
                status="ACTIVE",
                schema_version=1,
                definition_json={
                    "evidence_checklist": [
                        {"checklist_item_id": "photo", "label": "Photo"},
                        {"checklist_item_id": "id_doc", "label": "ID"},
                    ]
                },
                content_sha256="a" * 64,
                created_by="tester",
                updated_by="tester",
            )
        )
        connection.execute(
            update(casework_matters)
            .where(casework_matters.c.matter_id == matter_id)
            .values(assigned_playbook_version_id=version_id)
        )
    return version_id


def test_first_checklist_link_returns_inserted_true(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    ev = vault.upload(upload_command(matter_id), [b"hello"])
    _setup_checklist_playbook(migrated_engine, matter_id)
    link = vault.link_checklist(
        LinkEvidenceChecklistCommand(
            matter_id=matter_id,
            evidence_id=ev.evidence_id,
            checklist_item_id="photo",
            actor="tester",
            linked_at=datetime.now(UTC),
            source_channel="int",
        )
    )
    assert link.checklist_item_id == "photo"


def test_compatible_reuse_does_not_emit_duplicate_event(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    ev = vault.upload(upload_command(matter_id), [b"hello"])
    pin = _setup_checklist_playbook(migrated_engine, matter_id)
    now = datetime.now(UTC)
    vault.link_checklist(
        LinkEvidenceChecklistCommand(
            matter_id=matter_id,
            evidence_id=ev.evidence_id,
            checklist_item_id="photo",
            actor="tester",
            linked_at=now,
            source_channel="int",
        )
    )
    second = vault.link_checklist(
        LinkEvidenceChecklistCommand(
            matter_id=matter_id,
            evidence_id=ev.evidence_id,
            checklist_item_id="photo",
            actor="tester",
            linked_at=now,
            source_channel="int",
        )
    )
    assert second.playbook_version_id == pin
    assert second.linked_by == "tester"
    with migrated_engine.connect() as connection:
        linked = connection.scalar(
            select(func.count())
            .select_from(casework_audit_events)
            .where(casework_audit_events.c.event_type == "EVIDENCE_CHECKLIST_LINKED")
        )
    assert linked == 1


def test_conflicting_linked_by_fails_closed(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    ev = vault.upload(upload_command(matter_id), [b"hello"])
    pin = _setup_checklist_playbook(migrated_engine, matter_id)
    now = datetime.now(UTC)
    vault.link_checklist(
        LinkEvidenceChecklistCommand(
            matter_id=matter_id,
            evidence_id=ev.evidence_id,
            checklist_item_id="photo",
            actor="alice",
            linked_at=now,
            source_channel="int",
        )
    )
    from legal_ai.evidence.errors import ChecklistLinkConflict

    with pytest.raises(ChecklistLinkConflict):
        vault.link_checklist(
            LinkEvidenceChecklistCommand(
                matter_id=matter_id,
                evidence_id=ev.evidence_id,
                checklist_item_id="photo",
                actor="bob",
                linked_at=now,
                source_channel="int",
            )
        )
    with migrated_engine.connect() as connection:
        stored = connection.execute(
            select(casework_evidence_checklist_links.c.linked_by).where(
                casework_evidence_checklist_links.c.matter_id == matter_id,
                casework_evidence_checklist_links.c.playbook_version_id == pin,
                casework_evidence_checklist_links.c.checklist_item_id == "photo",
            )
        ).scalar_one()
    assert stored == "alice"
    with migrated_engine.connect() as connection:
        linked = connection.scalar(
            select(func.count())
            .select_from(casework_audit_events)
            .where(casework_audit_events.c.event_type == "EVIDENCE_CHECKLIST_LINKED")
        )
    assert linked == 1
    with migrated_engine.connect() as connection:
        conflict = connection.scalar(
            select(func.count())
            .select_from(casework_audit_events)
            .where(casework_audit_events.c.event_type == "EVIDENCE_PROVENANCE_CONFLICT")
        )
    assert conflict == 1


def test_conflicting_linked_at_fails_closed(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    ev = vault.upload(upload_command(matter_id), [b"hello"])
    pin = _setup_checklist_playbook(migrated_engine, matter_id)
    now = datetime.now(UTC)
    vault.link_checklist(
        LinkEvidenceChecklistCommand(
            matter_id=matter_id,
            evidence_id=ev.evidence_id,
            checklist_item_id="photo",
            actor="tester",
            linked_at=now,
            source_channel="int",
        )
    )
    from legal_ai.evidence.errors import ChecklistLinkConflict

    with pytest.raises(ChecklistLinkConflict):
        vault.link_checklist(
            LinkEvidenceChecklistCommand(
                matter_id=matter_id,
                evidence_id=ev.evidence_id,
                checklist_item_id="photo",
                actor="tester",
                linked_at=datetime.now(UTC),
                source_channel="int",
            )
        )
    with migrated_engine.connect() as connection:
        stored = connection.execute(
            select(casework_evidence_checklist_links.c.linked_at).where(
                casework_evidence_checklist_links.c.matter_id == matter_id,
                casework_evidence_checklist_links.c.playbook_version_id == pin,
                casework_evidence_checklist_links.c.checklist_item_id == "photo",
            )
        ).scalar_one()
    assert stored == now
    with migrated_engine.connect() as connection:
        linked = connection.scalar(
            select(func.count())
            .select_from(casework_audit_events)
            .where(casework_audit_events.c.event_type == "EVIDENCE_CHECKLIST_LINKED")
        )
    assert linked == 1
    with migrated_engine.connect() as connection:
        conflict = connection.scalar(
            select(func.count())
            .select_from(casework_audit_events)
            .where(casework_audit_events.c.event_type == "EVIDENCE_PROVENANCE_CONFLICT")
        )
    assert conflict == 1


def test_concurrent_compatible_checklist_insert(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    ev = vault.upload(upload_command(matter_id), [b"hello"])
    _setup_checklist_playbook(migrated_engine, matter_id)
    now = datetime.now(UTC)
    from threading import Thread

    results: list[object] = []

    def link() -> None:
        v = service(migrated_engine, tmp_path)
        r = v.link_checklist(
            LinkEvidenceChecklistCommand(
                matter_id=matter_id,
                evidence_id=ev.evidence_id,
                checklist_item_id="photo",
                actor="tester",
                linked_at=now,
                source_channel="int",
            )
        )
        results.append(r)

    t1, t2 = Thread(target=link), Thread(target=link)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert len(results) == 2
    with migrated_engine.connect() as connection:
        count = connection.scalar(
            select(func.count())
            .select_from(casework_evidence_checklist_links)
            .where(casework_evidence_checklist_links.c.matter_id == matter_id)
        )
    assert count == 1


def test_historical_version_link_preservation(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    ev = vault.upload(upload_command(matter_id), [b"hello"])
    v1 = uuid4()
    v2 = uuid4()
    with migrated_engine.begin() as connection:
        connection.execute(
            insert(playbooks).values(
                playbook_key="v-test",
                display_name="Version test",
                created_by="tester",
            )
        )
        connection.execute(
            insert(playbook_versions).values(
                playbook_version_id=v1,
                playbook_key="v-test",
                version=1,
                status="ACTIVE",
                schema_version=1,
                definition_json={
                    "evidence_checklist": [
                        {"checklist_item_id": "photo", "label": "Photo"},
                    ]
                },
                content_sha256="a" * 64,
                created_by="tester",
                updated_by="tester",
            )
        )
        connection.execute(
            update(casework_matters)
            .where(casework_matters.c.matter_id == matter_id)
            .values(assigned_playbook_version_id=v1)
        )
    v1_now = datetime.now(UTC)
    v1_link = vault.link_checklist(
        LinkEvidenceChecklistCommand(
            matter_id=matter_id,
            evidence_id=ev.evidence_id,
            checklist_item_id="photo",
            actor="tester",
            linked_at=v1_now,
            source_channel="int",
        )
    )
    assert v1_link.playbook_version_id == v1
    with migrated_engine.begin() as connection:
        connection.execute(
            insert(playbook_versions).values(
                playbook_version_id=v2,
                playbook_key="v-test",
                version=2,
                status="ACTIVE",
                schema_version=1,
                definition_json={
                    "evidence_checklist": [
                        {"checklist_item_id": "photo", "label": "Photo"},
                    ]
                },
                content_sha256="b" * 64,
                created_by="tester",
                updated_by="tester",
            )
        )
        connection.execute(
            update(casework_matters)
            .where(casework_matters.c.matter_id == matter_id)
            .values(assigned_playbook_version_id=v2)
        )
    v2_now = datetime.now(UTC)
    v2_link = vault.link_checklist(
        LinkEvidenceChecklistCommand(
            matter_id=matter_id,
            evidence_id=ev.evidence_id,
            checklist_item_id="photo",
            actor="tester",
            linked_at=v2_now,
            source_channel="int",
        )
    )
    assert v2_link.playbook_version_id == v2
    with migrated_engine.connect() as connection:
        v1_stored = (
            connection.execute(
                select(casework_evidence_checklist_links).where(
                    casework_evidence_checklist_links.c.matter_id == matter_id,
                    casework_evidence_checklist_links.c.playbook_version_id == v1,
                )
            )
            .mappings()
            .one()
        )
    assert v1_stored["linked_by"] == "tester"
    assert v1_stored["linked_at"] == v1_now
    with migrated_engine.connect() as connection:
        v2_stored = (
            connection.execute(
                select(casework_evidence_checklist_links).where(
                    casework_evidence_checklist_links.c.matter_id == matter_id,
                    casework_evidence_checklist_links.c.playbook_version_id == v2,
                )
            )
            .mappings()
            .one()
        )
    assert v2_stored["linked_by"] == "tester"
    v2_retry = vault.link_checklist(
        LinkEvidenceChecklistCommand(
            matter_id=matter_id,
            evidence_id=ev.evidence_id,
            checklist_item_id="photo",
            actor="tester",
            linked_at=v2_now,
            source_channel="int",
        )
    )
    assert v2_retry.playbook_version_id == v2
    with migrated_engine.connect() as connection:
        count = connection.scalar(
            select(func.count())
            .select_from(casework_evidence_checklist_links)
            .where(
                casework_evidence_checklist_links.c.matter_id == matter_id,
                casework_evidence_checklist_links.c.playbook_version_id == v2,
            )
        )
    assert count == 1
    with migrated_engine.connect() as connection:
        checklist_states = connection.scalar(
            select(func.count())
            .select_from(casework_checklist_states)
            .where(casework_checklist_states.c.matter_id == matter_id)
        )
    assert checklist_states == 0
    with migrated_engine.connect() as connection:
        total_linked = connection.scalar(
            select(func.count())
            .select_from(casework_audit_events)
            .where(
                casework_audit_events.c.matter_id == matter_id,
                casework_audit_events.c.event_type == "EVIDENCE_CHECKLIST_LINKED",
            )
        )
    assert total_linked == 2


def test_concurrent_conflicting_provenance(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    ev = vault.upload(upload_command(matter_id), [b"hello"])
    _setup_checklist_playbook(migrated_engine, matter_id)
    from threading import Thread

    results: list[object] = []
    errors: list[Exception] = []

    def link_alice() -> None:
        v = service(migrated_engine, tmp_path)
        try:
            r = v.link_checklist(
                LinkEvidenceChecklistCommand(
                    matter_id=matter_id,
                    evidence_id=ev.evidence_id,
                    checklist_item_id="photo",
                    actor="alice",
                    linked_at=datetime.now(UTC),
                    source_channel="int",
                )
            )
            results.append(r)
        except Exception as e:
            errors.append(e)

    def link_bob() -> None:
        v = service(migrated_engine, tmp_path)
        try:
            r = v.link_checklist(
                LinkEvidenceChecklistCommand(
                    matter_id=matter_id,
                    evidence_id=ev.evidence_id,
                    checklist_item_id="photo",
                    actor="bob",
                    linked_at=datetime.now(UTC),
                    source_channel="int",
                )
            )
            results.append(r)
        except Exception as e:
            errors.append(e)

    t1, t2 = Thread(target=link_alice), Thread(target=link_bob)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    with migrated_engine.connect() as connection:
        count = connection.scalar(
            select(func.count())
            .select_from(casework_evidence_checklist_links)
            .where(casework_evidence_checklist_links.c.matter_id == matter_id)
        )
        assert count == 1
        linked = connection.scalar(
            select(func.count())
            .select_from(casework_audit_events)
            .where(
                casework_audit_events.c.matter_id == matter_id,
                casework_audit_events.c.event_type == "EVIDENCE_CHECKLIST_LINKED",
            )
        )
        assert linked == 1
        conflict = connection.scalar(
            select(func.count())
            .select_from(casework_audit_events)
            .where(
                casework_audit_events.c.matter_id == matter_id,
                casework_audit_events.c.event_type == "EVIDENCE_PROVENANCE_CONFLICT",
            )
        )
        assert conflict == 1


def test_checklist_success_audit_rollback(migrated_engine: Engine, tmp_path: Path) -> None:
    matter_id = create_matter(migrated_engine)
    repo = EvidenceRepository(migrated_engine)
    vault = EvidenceService(repo, LocalArtifactStore(tmp_path))
    ev = vault.upload(upload_command(matter_id), [b"hello"])
    _setup_checklist_playbook(migrated_engine, matter_id)

    def fail_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    repo.casework.append_audit_event = fail_audit  # type: ignore[assignment]
    now = datetime.now(UTC)
    with pytest.raises(EvidenceAuditWriteFailed):
        vault.link_checklist(
            LinkEvidenceChecklistCommand(
                matter_id=matter_id,
                evidence_id=ev.evidence_id,
                checklist_item_id="photo",
                actor="tester",
                linked_at=now,
                source_channel="int",
            )
        )
    with migrated_engine.connect() as connection:
        link_count = connection.scalar(
            select(func.count())
            .select_from(casework_evidence_checklist_links)
            .where(casework_evidence_checklist_links.c.matter_id == matter_id)
        )
        assert link_count == 0
        audit_count = connection.scalar(
            select(func.count())
            .select_from(casework_audit_events)
            .where(
                casework_audit_events.c.matter_id == matter_id,
                casework_audit_events.c.event_type == "EVIDENCE_CHECKLIST_LINKED",
            )
        )
        assert audit_count == 0


def test_checklist_persistence_inconsistency(migrated_engine: Engine, tmp_path: Path) -> None:
    from legal_ai.evidence.errors import ChecklistLinkPersistenceError

    matter_id = create_matter(migrated_engine)
    vault = service(migrated_engine, tmp_path)
    ev = vault.upload(upload_command(matter_id), [b"hello"])
    _setup_checklist_playbook(migrated_engine, matter_id)

    repo = EvidenceRepository(migrated_engine)
    original_get = repo._get_checklist_link

    def simulate_inserted_row_disappears(*args: object, **kwargs: object) -> None:
        return None

    repo._get_checklist_link = simulate_inserted_row_disappears  # type: ignore[method-assign]
    vault._repo = repo

    now = datetime.now(UTC)
    with pytest.raises(ChecklistLinkPersistenceError):
        vault.link_checklist(
            LinkEvidenceChecklistCommand(
                matter_id=matter_id,
                evidence_id=ev.evidence_id,
                checklist_item_id="photo",
                actor="tester",
                linked_at=now,
                source_channel="int",
            )
        )

    repo._get_checklist_link = original_get  # type: ignore[method-assign]
    vault._repo = EvidenceRepository(migrated_engine)

    with migrated_engine.connect() as connection:
        cross_matter = connection.scalar(
            select(func.count())
            .select_from(casework_audit_events)
            .where(
                casework_audit_events.c.matter_id == matter_id,
                casework_audit_events.c.event_type == "ACTION_DENIED",
            )
        )
        assert cross_matter == 0
        linked = connection.scalar(
            select(func.count())
            .select_from(casework_audit_events)
            .where(
                casework_audit_events.c.matter_id == matter_id,
                casework_audit_events.c.event_type == "EVIDENCE_CHECKLIST_LINKED",
            )
        )
        assert linked == 0
        cleaned = connection.scalar(
            select(func.count())
            .select_from(casework_evidence_checklist_links)
            .where(casework_evidence_checklist_links.c.matter_id == matter_id)
        )
        assert cleaned == 0

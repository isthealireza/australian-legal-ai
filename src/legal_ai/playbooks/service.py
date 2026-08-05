"""Application service for Phase 2 Versioned Playbook Framework."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection

from legal_ai.casework.errors import (
    ClosedMatterMutationError,
    ConcurrencyConflictError,
    InvalidTransitionError,
)
from legal_ai.casework.models import MatterRecord
from legal_ai.casework.repository import CaseworkRepository
from legal_ai.casework.state_machine import assert_transition_allowed
from legal_ai.casework.types import (
    ActionAuthorityLevel,
    AuditEventType,
    CaseType,
    MatterStatus,
)
from legal_ai.playbooks.authority import assert_playbook_action_allowed
from legal_ai.playbooks.errors import (
    GroundingUnavailable,
    GroundingValidationFailed,
    PlaybookAssignmentError,
    PlaybookAuditWriteFailed,
    PlaybookAuthorityDenied,
    PlaybookValidationError,
    SeedHashConflictError,
    TransitionRequiredError,
)
from legal_ai.playbooks.grounding import GroundingActivationGate, require_grounding_gate
from legal_ai.playbooks.models import (
    ActivateVersionCommand,
    ApplyFallbackCommand,
    AssignPlaybookCommand,
    ChecklistStateRecord,
    CreateDraftCommand,
    DisqualifierRule,
    IntakeAnswerRecord,
    MarkUnsupportedCommand,
    PlaybookDefinitionPayload,
    PlaybookVersionRecord,
    RecordBlockingDisqualifierCommand,
    RejectAssignmentCommand,
    RetireVersionCommand,
    SeedDraftResult,
    UpdateDraftCommand,
    UpgradePlaybookCommand,
    UpsertChecklistStateCommand,
    UpsertIntakeAnswerCommand,
    validate_definition_payload,
)
from legal_ai.playbooks.repository import PlaybookRepository
from legal_ai.playbooks.rules import evaluate_rule, parse_rule_node
from legal_ai.playbooks.types import (
    PLAYBOOK_SCHEMA_VERSION,
    DisqualifierOutcome,
    EvaluationOutcome,
    EvaluationReason,
    IntakeValueType,
    PlaybookAuditEventType,
    PlaybookStatus,
    RuleResult,
)

# Test-only failure injection points for upgrade TX rollback tests.
# Production callers must leave failure_inject=None / unset.
_FAILURE_INJECT_POINTS = frozenset(
    {
        "after_snapshot",
        "after_live_delete",
        "after_pin_update",
        "after_audit",
    }
)


class PlaybookService:
    """Playbook registry and matter pin/assignment commands."""

    def __init__(
        self,
        playbook_repository: PlaybookRepository,
        casework_repository: CaseworkRepository,
        grounding_gate: GroundingActivationGate,
    ) -> None:
        self._playbooks = playbook_repository
        self._casework = casework_repository
        self._grounding_gate = require_grounding_gate(grounding_gate)

    def create_draft(self, command: CreateDraftCommand) -> PlaybookVersionRecord:
        payload = validate_definition_payload(command.definition)
        digest = payload.content_sha256()
        version_id = uuid4()
        with self._playbooks.transaction() as connection:
            self._playbooks.ensure_playbook_family(
                connection,
                playbook_key=command.playbook_key,
                display_name=command.display_name,
                created_by=command.actor,
            )
            version = self._playbooks.insert_draft_version(
                connection,
                playbook_version_id=version_id,
                playbook_key=command.playbook_key,
                version=command.version,
                schema_version=PLAYBOOK_SCHEMA_VERSION,
                definition_json=payload.to_canonical_dict(),
                content_sha256=digest,
                actor=command.actor,
            )
            self._append_playbook_audit(
                connection,
                event_id=uuid4(),
                playbook_key=version.playbook_key,
                version=version.version,
                playbook_version_id=version.playbook_version_id,
                actor=command.actor,
                event_type=PlaybookAuditEventType.PLAYBOOK_DRAFT_CREATED,
                correlation_id=command.correlation_id,
                row_version_after=version.row_version,
                metadata={
                    "command_type": "CreateDraft",
                    "content_sha256": digest,
                    "schema_version": PLAYBOOK_SCHEMA_VERSION,
                    "row_version": version.row_version,
                },
            )
            return version

    def update_draft(self, command: UpdateDraftCommand) -> PlaybookVersionRecord:
        payload = validate_definition_payload(command.definition)
        digest = payload.content_sha256()
        with self._playbooks.transaction() as connection:
            existing = self._playbooks.require_version(connection, command.playbook_version_id)
            if existing.status is not PlaybookStatus.DRAFT:
                raise PlaybookValidationError("only DRAFT versions may be updated")
            version = self._playbooks.update_draft(
                connection,
                playbook_version_id=command.playbook_version_id,
                expected_row_version=command.row_version,
                definition_json=payload.to_canonical_dict(),
                content_sha256=digest,
                actor=command.actor,
            )
            self._append_playbook_audit(
                connection,
                event_id=uuid4(),
                playbook_key=version.playbook_key,
                version=version.version,
                playbook_version_id=version.playbook_version_id,
                actor=command.actor,
                event_type=PlaybookAuditEventType.PLAYBOOK_DRAFT_UPDATED,
                correlation_id=command.correlation_id,
                row_version_after=version.row_version,
                metadata={
                    "command_type": "UpdateDraft",
                    "content_sha256": digest,
                    "schema_version": PLAYBOOK_SCHEMA_VERSION,
                    "row_version": version.row_version,
                },
            )
            return version

    def activate_version(self, command: ActivateVersionCommand) -> PlaybookVersionRecord:
        with self._playbooks.transaction() as connection:
            existing = self._playbooks.require_version(connection, command.playbook_version_id)
            if existing.status is not PlaybookStatus.DRAFT:
                raise PlaybookValidationError("only DRAFT versions may be activated")
            if existing.row_version != command.row_version:
                raise ConcurrencyConflictError(
                    f"playbook activate {command.playbook_version_id} conflict "
                    f"at {command.row_version}"
                )
            definition = validate_definition_payload(existing.definition_json)
            try:
                self._grounding_gate.assert_may_activate(
                    playbook_key=existing.playbook_key,
                    version=existing.version,
                    operational_class=definition.operational_class,
                    content_sha256=existing.content_sha256,
                )
            except (GroundingUnavailable, GroundingValidationFailed) as denied:
                self._record_activation_denied(
                    existing=existing,
                    actor=command.actor,
                    correlation_id=command.correlation_id,
                    error=denied,
                )
                raise

            activated_at = datetime.now(UTC)
            version = self._playbooks.activate_version(
                connection,
                playbook_version_id=command.playbook_version_id,
                expected_row_version=command.row_version,
                activated_by=command.actor,
                activated_at=activated_at,
                effective_from=command.effective_from,
            )
            self._append_playbook_audit(
                connection,
                event_id=uuid4(),
                playbook_key=version.playbook_key,
                version=version.version,
                playbook_version_id=version.playbook_version_id,
                actor=command.actor,
                event_type=PlaybookAuditEventType.PLAYBOOK_ACTIVATED,
                correlation_id=command.correlation_id,
                row_version_after=version.row_version,
                metadata={
                    "command_type": "ActivateVersion",
                    "content_sha256": version.content_sha256,
                    "from_status": PlaybookStatus.DRAFT.value,
                    "to_status": PlaybookStatus.ACTIVE.value,
                    "row_version": version.row_version,
                },
            )
            return version

    def retire_version(self, command: RetireVersionCommand) -> PlaybookVersionRecord:
        with self._playbooks.transaction() as connection:
            existing = self._playbooks.require_version(connection, command.playbook_version_id)
            if existing.status is not PlaybookStatus.ACTIVE:
                raise PlaybookValidationError("only ACTIVE versions may be retired")
            retired_at = datetime.now(UTC)
            version = self._playbooks.retire_version(
                connection,
                playbook_version_id=command.playbook_version_id,
                expected_row_version=command.row_version,
                retired_by=command.actor,
                retired_at=retired_at,
                retirement_reason_code=command.retirement_reason_code,
            )
            self._append_playbook_audit(
                connection,
                event_id=uuid4(),
                playbook_key=version.playbook_key,
                version=version.version,
                playbook_version_id=version.playbook_version_id,
                actor=command.actor,
                event_type=PlaybookAuditEventType.PLAYBOOK_RETIRED,
                correlation_id=command.correlation_id,
                row_version_after=version.row_version,
                metadata={
                    "command_type": "RetireVersion",
                    "reason_code": command.retirement_reason_code,
                    "from_status": PlaybookStatus.ACTIVE.value,
                    "to_status": PlaybookStatus.RETIRED.value,
                    "row_version": version.row_version,
                },
            )
            return version

    def seed_draft_definition(
        self,
        *,
        playbook_key: str,
        version: int,
        display_name: str,
        definition: dict[str, Any],
        actor: str,
        correlation_id: UUID | None = None,
    ) -> SeedDraftResult:
        """Validate and insert a DRAFT seed. Never activates. Idempotent on same hash."""

        payload = validate_definition_payload(definition)
        digest = payload.content_sha256()
        with self._playbooks.transaction() as connection:
            existing = self._playbooks.get_version_by_key_version(
                connection, playbook_key=playbook_key, version=version
            )
            if existing is not None:
                if existing.content_sha256 == digest:
                    self._append_playbook_audit(
                        connection,
                        event_id=uuid4(),
                        playbook_key=existing.playbook_key,
                        version=existing.version,
                        playbook_version_id=existing.playbook_version_id,
                        actor=actor,
                        event_type=PlaybookAuditEventType.PLAYBOOK_DRAFT_SEED_NOOP,
                        correlation_id=correlation_id,
                        row_version_after=existing.row_version,
                        metadata={
                            "command_type": "SeedDraft",
                            "content_sha256": digest,
                            "schema_version": PLAYBOOK_SCHEMA_VERSION,
                            "row_version": existing.row_version,
                        },
                    )
                    return SeedDraftResult(version=existing, already_present=True)
                raise SeedHashConflictError(
                    f"seed conflict for {playbook_key} v{version}: "
                    f"existing={existing.content_sha256} fixture={digest}"
                )

            self._playbooks.ensure_playbook_family(
                connection,
                playbook_key=playbook_key,
                display_name=display_name,
                created_by=actor,
            )
            created = self._playbooks.insert_draft_version(
                connection,
                playbook_version_id=uuid4(),
                playbook_key=playbook_key,
                version=version,
                schema_version=PLAYBOOK_SCHEMA_VERSION,
                definition_json=payload.to_canonical_dict(),
                content_sha256=digest,
                actor=actor,
            )
            self._append_playbook_audit(
                connection,
                event_id=uuid4(),
                playbook_key=created.playbook_key,
                version=created.version,
                playbook_version_id=created.playbook_version_id,
                actor=actor,
                event_type=PlaybookAuditEventType.PLAYBOOK_DRAFT_CREATED,
                correlation_id=correlation_id,
                row_version_after=created.row_version,
                metadata={
                    "command_type": "SeedDraft",
                    "content_sha256": digest,
                    "schema_version": PLAYBOOK_SCHEMA_VERSION,
                    "row_version": created.row_version,
                },
            )
            return SeedDraftResult(version=created, already_present=False)

    def generate_candidates(
        self,
        *,
        facts: dict[str, Any],
        matter_jurisdiction: str,
        case_type: str,
    ) -> list[PlaybookVersionRecord]:
        """Read-only ACTIVE eligibility MATCH candidates. No evaluation or audit."""

        merged = dict(facts)
        merged.setdefault("matter.jurisdiction", matter_jurisdiction)
        merged.setdefault("matter.case_type", case_type)
        with self._playbooks.transaction() as connection:
            active = self._playbooks.list_active_versions(connection)
        matches: list[PlaybookVersionRecord] = []
        for version in active:
            definition = validate_definition_payload(version.definition_json)
            result = evaluate_rule(definition.eligibility_rule(), merged)
            if result is RuleResult.MATCH:
                matches.append(version)
        # Repository already orders playbook_key ASC, version DESC.
        return matches

    def assign_playbook(self, command: AssignPlaybookCommand) -> MatterRecord:
        try:
            return self._assign_playbook(command)
        except (PlaybookAssignmentError, PlaybookAuthorityDenied) as denied:
            self._record_policy_denied(
                command_type="AssignPlaybook",
                matter_id=command.matter_id,
                actor=command.actor,
                source_channel=command.source_channel,
                correlation_id=command.correlation_id,
                error=denied,
                playbook_version_id=command.playbook_version_id,
            )
            raise

    def _assign_playbook(self, command: AssignPlaybookCommand) -> MatterRecord:
        with self._casework.transaction() as connection:
            matter = self._require_open_matter(connection, command.matter_id)
            if matter.row_version != command.row_version:
                raise ConcurrencyConflictError(
                    f"matter {command.matter_id} row_version conflict at {command.row_version}"
                )
            version = self._playbooks.require_version(connection, command.playbook_version_id)
            definition = self._assert_assignable(
                matter=matter,
                version=version,
                facts=command.facts,
                command_type="AssignPlaybook",
            )
            matched_disqualifier = self._matching_disqualifier(
                definition=definition,
                matter=matter,
                facts=command.facts,
            )
            if matched_disqualifier is not None:
                if matched_disqualifier.outcome is not DisqualifierOutcome.RESEARCH_AND_DRAFT_ONLY:
                    raise PlaybookAssignmentError(
                        "AssignPlaybook blocked by disqualifier "
                        f"{matched_disqualifier.disqualifier_id}"
                    )
                return self._route_disqualifier(
                    connection,
                    matter=matter,
                    version=version,
                    disqualifier=matched_disqualifier,
                    command_type="AssignPlaybook",
                    actor=command.actor,
                    source_channel=command.source_channel,
                    correlation_id=command.correlation_id,
                )
            primary_case_type = definition.supported_case_types[0]
            now = datetime.now(UTC)
            updated = self._casework.update_matter_pin(
                connection,
                matter_id=command.matter_id,
                expected_row_version=command.row_version,
                assigned_playbook_version_id=version.playbook_version_id,
                playbook_assigned_at=now,
                playbook_assigned_by=command.actor,
                updated_by=command.actor,
                case_type=primary_case_type,
            )
            evaluation_id = uuid4()
            self._playbooks.insert_evaluation(
                connection,
                evaluation_id=evaluation_id,
                matter_id=command.matter_id,
                occurred_at=now,
                actor=command.actor,
                outcome_code=EvaluationOutcome.ASSIGNED,
                reason_code=EvaluationReason.HUMAN_ASSIGNED,
                selected_playbook_version_id=version.playbook_version_id,
                matter_row_version_observed=command.row_version,
                notes=None,
                correlation_id=command.correlation_id,
                candidates=[(version.playbook_version_id, 1, RuleResult.MATCH)],
            )
            self._append_casework_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.PLAYBOOK_ASSIGNED,
                entity_type="playbook_version",
                entity_id=version.playbook_version_id,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "AssignPlaybook",
                    "playbook_key": version.playbook_key,
                    "playbook_version_id": str(version.playbook_version_id),
                    "playbook_version": version.version,
                    "evaluation_id": str(evaluation_id),
                    "row_version": updated.row_version,
                },
            )
            return updated

    def reject_assignment(self, command: RejectAssignmentCommand) -> MatterRecord:
        with self._casework.transaction() as connection:
            matter = self._require_open_matter(connection, command.matter_id)
            if matter.row_version != command.row_version:
                raise ConcurrencyConflictError(
                    f"matter {command.matter_id} row_version conflict at {command.row_version}"
                )
            now = datetime.now(UTC)
            candidates: list[tuple[UUID, int, RuleResult]] = []
            selected: UUID | None = None
            if command.playbook_version_id is not None:
                selected = command.playbook_version_id
                candidates = [(command.playbook_version_id, 1, RuleResult.MATCH)]
            evaluation_id = uuid4()
            self._playbooks.insert_evaluation(
                connection,
                evaluation_id=evaluation_id,
                matter_id=command.matter_id,
                occurred_at=now,
                actor=command.actor,
                outcome_code=EvaluationOutcome.ASSIGNMENT_REJECTED,
                reason_code=EvaluationReason.HUMAN_REJECTED,
                selected_playbook_version_id=selected,
                matter_row_version_observed=command.row_version,
                notes=command.reason[:512],
                correlation_id=command.correlation_id,
                candidates=candidates,
            )
            self._append_casework_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.PLAYBOOK_ASSIGNMENT_REJECTED,
                entity_type="matter",
                entity_id=command.matter_id,
                correlation_id=command.correlation_id,
                reason=command.reason,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "RejectAssignment",
                    "evaluation_id": str(evaluation_id),
                    "reason_code": EvaluationReason.HUMAN_REJECTED.value,
                    "row_version": matter.row_version,
                },
            )
            return matter

    def apply_fallback(self, command: ApplyFallbackCommand) -> MatterRecord:
        matter: MatterRecord | None = None
        try:
            with self._casework.transaction() as connection:
                matter = self._require_open_matter(connection, command.matter_id)
                if matter.row_version != command.row_version:
                    raise ConcurrencyConflictError(
                        f"matter {command.matter_id} row_version conflict at {command.row_version}"
                    )
                assert_transition_allowed(
                    current=matter.status,
                    target=command.target_status,
                    case_type=matter.case_type,
                    reopen=False,
                )

                now = datetime.now(UTC)
                updated = self._casework.update_matter_optimistic(
                    connection,
                    matter_id=command.matter_id,
                    expected_row_version=command.row_version,
                    values={
                        "status": command.target_status.value,
                        "updated_by": command.actor,
                    },
                )
                evaluation_id = uuid4()
                self._playbooks.insert_evaluation(
                    connection,
                    evaluation_id=evaluation_id,
                    matter_id=command.matter_id,
                    occurred_at=now,
                    actor=command.actor,
                    outcome_code=command.outcome_code,
                    reason_code=command.reason_code,
                    selected_playbook_version_id=None,
                    matter_row_version_observed=command.row_version,
                    notes=command.notes,
                    correlation_id=command.correlation_id,
                    candidates=[
                        (vid, idx, RuleResult.MATCH)
                        for idx, vid in enumerate(command.candidate_version_ids, start=1)
                    ],
                )
                self._append_casework_audit(
                    connection,
                    event_id=uuid4(),
                    matter_id=command.matter_id,
                    actor=command.actor,
                    event_type=AuditEventType.PLAYBOOK_FALLBACK_APPLIED,
                    entity_type="matter",
                    entity_id=command.matter_id,
                    correlation_id=command.correlation_id,
                    reason=None,
                    source_channel=command.source_channel,
                    metadata={
                        "command_type": "ApplyFallback",
                        "from_status": matter.status.value,
                        "to_status": command.target_status.value,
                        "outcome_code": command.outcome_code.value,
                        "reason_code": command.reason_code.value,
                        "evaluation_id": str(evaluation_id),
                        "row_version": updated.row_version,
                    },
                )
                return updated
        except InvalidTransitionError as invalid_transition:
            if matter is None:
                raise
            message = (
                "fallback status transition not allowed: "
                f"{matter.status.value} -> {command.target_status.value}"
            )
            pending_error = TransitionRequiredError(message)
            evaluation_id = uuid4()
            try:
                with self._casework.independent_transaction() as connection:
                    self._playbooks.insert_evaluation(
                        connection,
                        evaluation_id=evaluation_id,
                        matter_id=command.matter_id,
                        occurred_at=datetime.now(UTC),
                        actor=command.actor,
                        outcome_code=command.outcome_code,
                        reason_code=command.reason_code,
                        selected_playbook_version_id=None,
                        matter_row_version_observed=command.row_version,
                        notes=command.notes,
                        correlation_id=command.correlation_id,
                        candidates=[
                            (vid, idx, RuleResult.MATCH)
                            for idx, vid in enumerate(command.candidate_version_ids, start=1)
                        ],
                    )
                    self._append_casework_audit(
                        connection,
                        event_id=uuid4(),
                        matter_id=command.matter_id,
                        actor=command.actor,
                        event_type=AuditEventType.ACTION_DENIED,
                        entity_type="matter",
                        entity_id=command.matter_id,
                        correlation_id=command.correlation_id,
                        reason=None,
                        source_channel=command.source_channel,
                        metadata={
                            "command_type": "ApplyFallback",
                            "from_status": matter.status.value,
                            "to_status": command.target_status.value,
                            "outcome_code": command.outcome_code.value,
                            "reason_code": command.reason_code.value,
                            "evaluation_id": str(evaluation_id),
                            "row_version": matter.row_version,
                        },
                    )
            except Exception:
                raise PlaybookAuditWriteFailed(
                    "fallback rejection evaluation/audit persistence failed"
                ) from pending_error
            raise TransitionRequiredError(
                message,
                evaluation_id=evaluation_id,
            ) from invalid_transition

    def mark_unsupported(self, command: MarkUnsupportedCommand) -> MatterRecord:
        try:
            return self._mark_unsupported(command)
        except (PlaybookAssignmentError, PlaybookAuthorityDenied) as denied:
            self._record_policy_denied(
                command_type="MarkUnsupported",
                matter_id=command.matter_id,
                actor=command.actor,
                source_channel=command.source_channel,
                correlation_id=command.correlation_id,
                error=denied,
            )
            raise

    def _mark_unsupported(self, command: MarkUnsupportedCommand) -> MatterRecord:
        with self._casework.transaction() as connection:
            matter = self._require_open_matter(connection, command.matter_id)
            if matter.assigned_playbook_version_id is not None:
                raise PlaybookAssignmentError(
                    "MarkUnsupported refused while a playbook pin is present"
                )
            if matter.row_version != command.row_version:
                raise ConcurrencyConflictError(
                    f"matter {command.matter_id} row_version conflict at {command.row_version}"
                )
            target_status = MatterStatus.RESEARCH_AND_DRAFT_ONLY
            assert_transition_allowed(
                current=matter.status,
                target=target_status,
                case_type=CaseType.UNSUPPORTED,
                reopen=False,
            )
            updated = self._casework.update_matter_optimistic(
                connection,
                matter_id=command.matter_id,
                expected_row_version=command.row_version,
                values={
                    "case_type": CaseType.UNSUPPORTED.value,
                    "status": target_status.value,
                    "updated_by": command.actor,
                },
            )
            self._append_casework_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.PLAYBOOK_UNSUPPORTED_MARKED,
                entity_type="matter",
                entity_id=command.matter_id,
                correlation_id=command.correlation_id,
                reason=command.reason,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "MarkUnsupported",
                    "from_status": matter.status.value,
                    "to_status": target_status.value,
                    "row_version": updated.row_version,
                },
            )
            return updated

    def upgrade_playbook(
        self,
        command: UpgradePlaybookCommand,
        *,
        failure_inject: str | None = None,
    ) -> MatterRecord:
        """Atomic upgrade TX. ``failure_inject`` is test-only (production: None)."""

        if failure_inject is not None and failure_inject not in _FAILURE_INJECT_POINTS:
            raise PlaybookValidationError(f"unknown failure_inject point: {failure_inject}")

        try:
            return self._upgrade_playbook(command, failure_inject=failure_inject)
        except (PlaybookAssignmentError, PlaybookAuthorityDenied) as denied:
            self._record_policy_denied(
                command_type="UpgradePlaybook",
                matter_id=command.matter_id,
                actor=command.actor,
                source_channel=command.source_channel,
                correlation_id=command.correlation_id,
                error=denied,
                playbook_version_id=command.target_playbook_version_id,
            )
            raise

    def _upgrade_playbook(
        self,
        command: UpgradePlaybookCommand,
        *,
        failure_inject: str | None,
    ) -> MatterRecord:

        with self._casework.transaction() as connection:
            # 1. Lock matter; verify row_version
            matter = self._casework.lock_matter(connection, command.matter_id)
            if matter.status is MatterStatus.CLOSED:
                raise ClosedMatterMutationError("UpgradePlaybook is not allowed on CLOSED matters")
            if matter.row_version != command.row_version:
                raise ConcurrencyConflictError(
                    f"matter {command.matter_id} row_version conflict at {command.row_version}"
                )

            # 2. Validate current pin
            if matter.assigned_playbook_version_id is None:
                raise PlaybookAssignmentError("upgrade requires an existing playbook pin")
            current = self._playbooks.require_version(
                connection, matter.assigned_playbook_version_id
            )

            # 3. Validate target ACTIVE same key
            target = self._playbooks.require_version(connection, command.target_playbook_version_id)
            if target.status is not PlaybookStatus.ACTIVE:
                raise PlaybookAssignmentError("upgrade target must be ACTIVE")
            if target.playbook_key != current.playbook_key:
                raise PlaybookAssignmentError("upgrade target must share the same playbook_key")
            if target.playbook_version_id == current.playbook_version_id:
                raise PlaybookAssignmentError("upgrade target must differ from current pin")

            # 4. Compatibility
            definition = self._assert_assignable(
                matter=matter,
                version=target,
                facts=command.facts,
                command_type="UpgradePlaybook",
            )
            matched_disqualifier = self._matching_disqualifier(
                definition=definition,
                matter=matter,
                facts=command.facts,
            )
            if matched_disqualifier is not None:
                if matched_disqualifier.outcome is not DisqualifierOutcome.RESEARCH_AND_DRAFT_ONLY:
                    raise PlaybookAssignmentError(
                        "UpgradePlaybook blocked by disqualifier "
                        f"{matched_disqualifier.disqualifier_id}"
                    )
                return self._route_disqualifier(
                    connection,
                    matter=matter,
                    version=target,
                    disqualifier=matched_disqualifier,
                    command_type="UpgradePlaybook",
                    actor=command.actor,
                    source_channel=command.source_channel,
                    correlation_id=command.correlation_id,
                )

            now = datetime.now(UTC)
            correlation_id = command.correlation_id or uuid4()

            # 5–6. Snapshot intake/checklist → history
            self._playbooks.snapshot_intake_to_history(
                connection,
                matter_id=command.matter_id,
                playbook_version_id=current.playbook_version_id,
                superseded_at=now,
                superseded_by=command.actor,
                superseded_by_playbook_version_id=target.playbook_version_id,
                upgrade_correlation_id=correlation_id,
            )
            self._playbooks.snapshot_checklist_to_history(
                connection,
                matter_id=command.matter_id,
                playbook_version_id=current.playbook_version_id,
                superseded_at=now,
                superseded_by=command.actor,
                superseded_by_playbook_version_id=target.playbook_version_id,
                upgrade_correlation_id=correlation_id,
            )
            self._maybe_inject(failure_inject, "after_snapshot")

            # 7. Delete live intake/checklist for current pin
            self._playbooks.delete_live_intake_and_checklist(
                connection,
                matter_id=command.matter_id,
                playbook_version_id=current.playbook_version_id,
            )
            self._maybe_inject(failure_inject, "after_live_delete")

            # 8. Update pin (no remap — step 9)
            updated = self._casework.update_matter_pin(
                connection,
                matter_id=command.matter_id,
                expected_row_version=command.row_version,
                assigned_playbook_version_id=target.playbook_version_id,
                playbook_assigned_at=now,
                playbook_assigned_by=command.actor,
                updated_by=command.actor,
            )
            self._maybe_inject(failure_inject, "after_pin_update")

            # 10. Evaluation + PLAYBOOK_UPGRADED audit
            evaluation_id = uuid4()
            self._playbooks.insert_evaluation(
                connection,
                evaluation_id=evaluation_id,
                matter_id=command.matter_id,
                occurred_at=now,
                actor=command.actor,
                outcome_code=EvaluationOutcome.UPGRADED,
                reason_code=EvaluationReason.HUMAN_UPGRADED,
                selected_playbook_version_id=target.playbook_version_id,
                matter_row_version_observed=command.row_version,
                notes=None,
                correlation_id=correlation_id,
                candidates=[(target.playbook_version_id, 1, RuleResult.MATCH)],
            )
            self._append_casework_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.PLAYBOOK_UPGRADED,
                entity_type="playbook_version",
                entity_id=target.playbook_version_id,
                correlation_id=correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "UpgradePlaybook",
                    "from_playbook_version_id": str(current.playbook_version_id),
                    "to_playbook_version_id": str(target.playbook_version_id),
                    "playbook_key": target.playbook_key,
                    "evaluation_id": str(evaluation_id),
                    "row_version": updated.row_version,
                },
            )
            self._maybe_inject(failure_inject, "after_audit")
            return updated

    def record_blocking_disqualifier(
        self,
        command: RecordBlockingDisqualifierCommand,
    ) -> MatterRecord:
        try:
            return self._record_blocking_disqualifier(command)
        except (PlaybookAssignmentError, PlaybookAuthorityDenied) as denied:
            self._record_policy_denied(
                command_type="RecordBlockingDisqualifier",
                matter_id=command.matter_id,
                actor=command.actor,
                source_channel=command.source_channel,
                correlation_id=command.correlation_id,
                error=denied,
            )
            raise

    def _record_blocking_disqualifier(
        self,
        command: RecordBlockingDisqualifierCommand,
    ) -> MatterRecord:
        with self._casework.transaction() as connection:
            matter = self._require_open_matter(connection, command.matter_id)
            if matter.assigned_playbook_version_id is None:
                raise PlaybookAssignmentError(
                    "RecordBlockingDisqualifier requires a pinned playbook"
                )
            if matter.row_version != command.row_version:
                raise ConcurrencyConflictError(
                    f"matter {command.matter_id} row_version conflict at {command.row_version}"
                )
            pin = self._playbooks.require_version(connection, matter.assigned_playbook_version_id)
            definition = validate_definition_payload(pin.definition_json)
            disqualifier = next(
                (
                    item
                    for item in definition.disqualifiers
                    if item.disqualifier_id == command.disqualifier_id
                ),
                None,
            )
            if disqualifier is None:
                raise PlaybookAssignmentError(
                    f"disqualifier_id not in pinned definition: {command.disqualifier_id}"
                )
            disqualifier_result = evaluate_rule(
                parse_rule_node(disqualifier.rule),
                self._trusted_matter_facts(matter=matter, facts=command.facts),
            )
            if disqualifier_result is not RuleResult.MATCH:
                raise PlaybookAssignmentError(
                    "pinned disqualifier requires MATCH, got "
                    f"{disqualifier_result.value}: {command.disqualifier_id}"
                )
            now = datetime.now(UTC)
            updated = matter
            target_status = (
                MatterStatus.RESEARCH_AND_DRAFT_ONLY
                if disqualifier.outcome is DisqualifierOutcome.RESEARCH_AND_DRAFT_ONLY
                else None
            )
            if target_status is not None and target_status is not matter.status:
                assert_transition_allowed(
                    current=matter.status,
                    target=target_status,
                    case_type=matter.case_type,
                    reopen=False,
                )
                updated = self._casework.update_matter_optimistic(
                    connection,
                    matter_id=command.matter_id,
                    expected_row_version=command.row_version,
                    values={
                        "status": target_status.value,
                        "updated_by": command.actor,
                    },
                )
            evaluation_id = uuid4()
            self._playbooks.insert_evaluation(
                connection,
                evaluation_id=evaluation_id,
                matter_id=command.matter_id,
                occurred_at=now,
                actor=command.actor,
                outcome_code=command.outcome_code,
                reason_code=EvaluationReason.DISQUALIFIER_MATCHED,
                selected_playbook_version_id=pin.playbook_version_id,
                matter_row_version_observed=command.row_version,
                notes=command.notes,
                correlation_id=command.correlation_id,
                candidates=[(pin.playbook_version_id, 1, RuleResult.MATCH)],
            )
            self._append_casework_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.ACTION_DENIED,
                entity_type="playbook_version",
                entity_id=pin.playbook_version_id,
                correlation_id=command.correlation_id,
                reason=command.disqualifier_id,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "RecordBlockingDisqualifier",
                    "playbook_key": pin.playbook_key,
                    "playbook_version_id": str(pin.playbook_version_id),
                    "playbook_version": pin.version,
                    "reason_code": command.disqualifier_id,
                    "outcome_code": command.outcome_code.value,
                    "evaluation_id": str(evaluation_id),
                    "from_status": matter.status.value,
                    **({"to_status": target_status.value} if target_status is not None else {}),
                    "row_version": updated.row_version,
                },
            )
            return updated

    def upsert_intake_answer(self, command: UpsertIntakeAnswerCommand) -> IntakeAnswerRecord:
        try:
            return self._upsert_intake_answer(command)
        except (PlaybookAssignmentError, PlaybookAuthorityDenied) as denied:
            self._record_policy_denied(
                command_type="UpsertIntakeAnswer",
                matter_id=command.matter_id,
                actor=command.actor,
                source_channel=command.source_channel,
                correlation_id=command.correlation_id,
                error=denied,
            )
            raise

    def _upsert_intake_answer(self, command: UpsertIntakeAnswerCommand) -> IntakeAnswerRecord:
        with self._casework.transaction() as connection:
            matter = self._require_open_matter(connection, command.matter_id)
            if matter.assigned_playbook_version_id is None:
                raise PlaybookAssignmentError("intake requires an assigned playbook pin")
            version = self._playbooks.require_version(
                connection, matter.assigned_playbook_version_id
            )
            definition = validate_definition_payload(version.definition_json)
            self._assert_pinned_ops_allowed(
                matter=matter,
                version=version,
                definition=definition,
                command_type="UpsertIntakeAnswer",
            )
            question = next(
                (q for q in definition.intake_questions if q.question_id == command.question_id),
                None,
            )
            if question is None:
                raise PlaybookValidationError(
                    f"question_id not in pinned definition: {command.question_id}"
                )
            if command.value_type is not question.value_type:
                raise PlaybookValidationError("intake value_type does not match question")
            self._validate_intake_value(command, question.enum_codes)
            answer = self._playbooks.upsert_intake_answer(
                connection,
                matter_id=command.matter_id,
                playbook_version_id=version.playbook_version_id,
                question_id=command.question_id,
                value_type=command.value_type,
                value_boolean=command.value_boolean,
                value_text=command.value_text,
                value_date=command.value_date,
                value_enum_code=command.value_enum_code,
                answered_by=command.actor,
                answered_at=datetime.now(UTC),
                expected_row_version=command.expected_row_version,
            )
            self._append_casework_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.INTAKE_ANSWER_UPSERTED,
                entity_type="intake_answer",
                entity_id=None,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "UpsertIntakeAnswer",
                    "question_id": command.question_id,
                    "playbook_version_id": str(version.playbook_version_id),
                    "row_version": answer.row_version,
                },
            )
            return answer

    def upsert_checklist_state(
        self,
        command: UpsertChecklistStateCommand,
    ) -> ChecklistStateRecord:
        try:
            return self._upsert_checklist_state(command)
        except (PlaybookAssignmentError, PlaybookAuthorityDenied) as denied:
            self._record_policy_denied(
                command_type="UpsertChecklistState",
                matter_id=command.matter_id,
                actor=command.actor,
                source_channel=command.source_channel,
                correlation_id=command.correlation_id,
                error=denied,
            )
            raise

    def _upsert_checklist_state(
        self,
        command: UpsertChecklistStateCommand,
    ) -> ChecklistStateRecord:
        with self._casework.transaction() as connection:
            matter = self._require_open_matter(connection, command.matter_id)
            if matter.assigned_playbook_version_id is None:
                raise PlaybookAssignmentError("checklist requires an assigned playbook pin")
            version = self._playbooks.require_version(
                connection, matter.assigned_playbook_version_id
            )
            definition = validate_definition_payload(version.definition_json)
            self._assert_pinned_ops_allowed(
                matter=matter,
                version=version,
                definition=definition,
                command_type="UpsertChecklistState",
            )
            item = next(
                (
                    i
                    for i in definition.evidence_checklist
                    if i.checklist_item_id == command.checklist_item_id
                ),
                None,
            )
            if item is None:
                raise PlaybookValidationError(
                    f"checklist_item_id not in pinned definition: {command.checklist_item_id}"
                )
            del item
            state = self._playbooks.upsert_checklist_state(
                connection,
                matter_id=command.matter_id,
                playbook_version_id=version.playbook_version_id,
                checklist_item_id=command.checklist_item_id,
                status=command.status,
                note=command.note,
                updated_by=command.actor,
                updated_at=datetime.now(UTC),
                expected_row_version=command.expected_row_version,
            )
            self._append_casework_audit(
                connection,
                event_id=uuid4(),
                matter_id=command.matter_id,
                actor=command.actor,
                event_type=AuditEventType.CHECKLIST_STATE_UPSERTED,
                entity_type="checklist_state",
                entity_id=None,
                correlation_id=command.correlation_id,
                reason=None,
                source_channel=command.source_channel,
                metadata={
                    "command_type": "UpsertChecklistState",
                    "checklist_item_id": command.checklist_item_id,
                    "playbook_version_id": str(version.playbook_version_id),
                    "row_version": state.row_version,
                },
            )
            return state

    def _assert_assignable(
        self,
        *,
        matter: MatterRecord,
        version: PlaybookVersionRecord,
        facts: dict[str, Any],
        command_type: str,
    ) -> PlaybookDefinitionPayload:
        if version.status is not PlaybookStatus.ACTIVE:
            raise PlaybookAssignmentError(f"{command_type} requires an ACTIVE playbook version")
        definition = validate_definition_payload(version.definition_json)
        assert_playbook_action_allowed(
            required=ActionAuthorityLevel.L1,
            matter_ceiling=matter.action_authority_ceiling,
            playbook_max_authority=definition.max_action_authority_level,
            playbook_status=version.status,
            command_type=command_type,
        )
        if matter.jurisdiction not in definition.jurisdiction_codes:
            raise PlaybookAssignmentError("matter jurisdiction incompatible with playbook")
        if matter.case_type not in definition.supported_case_types and matter.case_type not in {
            CaseType.UNASSIGNED,
            CaseType.SUPPORTED_PENDING_PLAYBOOK,
        }:
            raise PlaybookAssignmentError("matter case_type incompatible with playbook")
        merged = self._trusted_matter_facts(matter=matter, facts=facts)
        eligibility = evaluate_rule(definition.eligibility_rule(), merged)
        if eligibility is not RuleResult.MATCH:
            raise PlaybookAssignmentError(
                f"{command_type} requires eligibility MATCH, got {eligibility.value}"
            )
        return definition

    @staticmethod
    def _matching_disqualifier(
        *,
        definition: PlaybookDefinitionPayload,
        matter: MatterRecord,
        facts: dict[str, Any],
    ) -> DisqualifierRule | None:
        merged = PlaybookService._trusted_matter_facts(matter=matter, facts=facts)
        for disqualifier in definition.disqualifiers:
            result = evaluate_rule(parse_rule_node(disqualifier.rule), merged)
            if result is RuleResult.MATCH:
                return disqualifier
        return None

    @staticmethod
    def _trusted_matter_facts(
        *,
        matter: MatterRecord,
        facts: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(facts)
        merged.update(
            {
                "matter.jurisdiction": matter.jurisdiction.value,
                "matter.case_type": matter.case_type.value,
                "matter.status": matter.status.value,
                "matter.risk_level": matter.risk_level.value,
            }
        )
        return merged

    def _route_disqualifier(
        self,
        connection: Connection,
        *,
        matter: MatterRecord,
        version: PlaybookVersionRecord,
        disqualifier: DisqualifierRule,
        command_type: str,
        actor: str,
        source_channel: str,
        correlation_id: UUID | None,
    ) -> MatterRecord:
        target_status = MatterStatus.RESEARCH_AND_DRAFT_ONLY
        assert_transition_allowed(
            current=matter.status,
            target=target_status,
            case_type=matter.case_type,
            reopen=False,
        )
        now = datetime.now(UTC)
        updated = self._casework.update_matter_optimistic(
            connection,
            matter_id=matter.matter_id,
            expected_row_version=matter.row_version,
            values={
                "status": target_status.value,
                "updated_by": actor,
            },
        )
        evaluation_id = uuid4()
        self._playbooks.insert_evaluation(
            connection,
            evaluation_id=evaluation_id,
            matter_id=matter.matter_id,
            occurred_at=now,
            actor=actor,
            outcome_code=EvaluationOutcome.BLOCKING_DISQUALIFIER,
            reason_code=EvaluationReason.DISQUALIFIER_MATCHED,
            selected_playbook_version_id=version.playbook_version_id,
            matter_row_version_observed=matter.row_version,
            notes=None,
            correlation_id=correlation_id,
            candidates=[(version.playbook_version_id, 1, RuleResult.MATCH)],
        )
        metadata: dict[str, object] = {
            "command_type": command_type,
            "playbook_key": version.playbook_key,
            "playbook_version_id": str(version.playbook_version_id),
            "playbook_version": version.version,
            "from_status": matter.status.value,
            "to_status": target_status.value,
            "outcome_code": EvaluationOutcome.BLOCKING_DISQUALIFIER.value,
            "reason_code": EvaluationReason.DISQUALIFIER_MATCHED.value,
            "evaluation_id": str(evaluation_id),
            "row_version": updated.row_version,
        }
        if matter.assigned_playbook_version_id is not None:
            metadata["from_playbook_version_id"] = str(matter.assigned_playbook_version_id)
        self._append_casework_audit(
            connection,
            event_id=uuid4(),
            matter_id=matter.matter_id,
            actor=actor,
            event_type=AuditEventType.ACTION_DENIED,
            entity_type="playbook_version",
            entity_id=version.playbook_version_id,
            correlation_id=correlation_id,
            reason=disqualifier.disqualifier_id,
            source_channel=source_channel,
            metadata=metadata,
        )
        return updated

    def _assert_pinned_ops_allowed(
        self,
        *,
        matter: MatterRecord,
        version: PlaybookVersionRecord,
        definition: PlaybookDefinitionPayload,
        command_type: str,
    ) -> None:
        assert_playbook_action_allowed(
            required=ActionAuthorityLevel.L1,
            matter_ceiling=matter.action_authority_ceiling,
            playbook_max_authority=definition.max_action_authority_level,
            playbook_status=version.status,
            command_type=command_type,
        )

    def _require_open_matter(self, connection: Connection, matter_id: UUID) -> MatterRecord:
        matter = self._casework.require_matter(connection, matter_id)
        if matter.status is MatterStatus.CLOSED:
            raise ClosedMatterMutationError("playbook mutation is not allowed on CLOSED matters")
        return matter

    @staticmethod
    def _validate_intake_value(
        command: UpsertIntakeAnswerCommand,
        enum_codes: tuple[str, ...],
    ) -> None:
        if command.value_type is IntakeValueType.BOOLEAN:
            if (
                command.value_boolean is None
                or command.value_text is not None
                or command.value_date is not None
                or command.value_enum_code is not None
            ):
                raise PlaybookValidationError("BOOLEAN intake requires only value_boolean")
        elif command.value_type is IntakeValueType.TEXT:
            if (
                command.value_text is None
                or command.value_boolean is not None
                or command.value_date is not None
                or command.value_enum_code is not None
            ):
                raise PlaybookValidationError("TEXT intake requires only value_text")
        elif command.value_type is IntakeValueType.DATE:
            if (
                command.value_date is None
                or command.value_boolean is not None
                or command.value_text is not None
                or command.value_enum_code is not None
            ):
                raise PlaybookValidationError("DATE intake requires only value_date")
        elif command.value_type is IntakeValueType.ENUM:
            if (
                command.value_enum_code is None
                or command.value_boolean is not None
                or command.value_text is not None
                or command.value_date is not None
            ):
                raise PlaybookValidationError("ENUM intake requires only value_enum_code")
            if command.value_enum_code not in enum_codes:
                raise PlaybookValidationError("enum code not allowed for question")
        else:
            raise PlaybookValidationError(f"unsupported intake value_type {command.value_type}")

    def _record_activation_denied(
        self,
        *,
        existing: PlaybookVersionRecord,
        actor: str,
        correlation_id: UUID | None,
        error: Exception,
    ) -> None:
        try:
            with self._playbooks.independent_transaction() as connection:
                self._playbooks.append_playbook_audit(
                    connection,
                    event_id=uuid4(),
                    playbook_key=existing.playbook_key,
                    version=existing.version,
                    playbook_version_id=existing.playbook_version_id,
                    actor=actor,
                    event_type=PlaybookAuditEventType.PLAYBOOK_ACTIVATION_DENIED,
                    correlation_id=correlation_id,
                    row_version_after=existing.row_version,
                    metadata={
                        "command_type": "ActivateVersion",
                        "grounding_error_type": type(error).__name__,
                        "content_sha256": existing.content_sha256,
                        "row_version": existing.row_version,
                    },
                )
        except Exception:
            raise PlaybookAuditWriteFailed("activation denied audit insert failed") from error

    def _record_policy_denied(
        self,
        *,
        command_type: str,
        matter_id: UUID,
        actor: str,
        source_channel: str,
        correlation_id: UUID | None,
        error: Exception,
        playbook_version_id: UUID | None = None,
    ) -> None:
        try:
            with self._casework.independent_transaction() as connection:
                matter = self._casework.require_matter(connection, matter_id)
                relevant_version_id = playbook_version_id or matter.assigned_playbook_version_id
                version = (
                    self._playbooks.require_version(connection, relevant_version_id)
                    if relevant_version_id is not None
                    else None
                )
                metadata: dict[str, object] = {
                    "command_type": command_type,
                    "reason_code": type(error).__name__,
                    "row_version": matter.row_version,
                }
                if version is not None:
                    metadata.update(
                        {
                            "playbook_key": version.playbook_key,
                            "playbook_version_id": str(version.playbook_version_id),
                            "playbook_version": version.version,
                        }
                    )
                if matter.assigned_playbook_version_id is not None:
                    metadata["from_playbook_version_id"] = str(matter.assigned_playbook_version_id)
                self._append_casework_audit(
                    connection,
                    event_id=uuid4(),
                    matter_id=matter_id,
                    actor=actor,
                    event_type=AuditEventType.ACTION_DENIED,
                    entity_type="playbook_version" if version is not None else "matter",
                    entity_id=version.playbook_version_id if version is not None else matter_id,
                    correlation_id=correlation_id,
                    reason=str(error)[:2000],
                    source_channel=source_channel,
                    metadata=metadata,
                )
        except Exception:
            raise PlaybookAuditWriteFailed(
                f"policy denial audit insert failed for {command_type}"
            ) from error

    def _append_playbook_audit(
        self,
        connection: Connection,
        *,
        event_id: UUID,
        playbook_key: str,
        version: int,
        playbook_version_id: UUID,
        actor: str,
        event_type: PlaybookAuditEventType,
        correlation_id: UUID | None,
        row_version_after: int | None,
        metadata: dict[str, object],
    ) -> None:
        try:
            self._playbooks.append_playbook_audit(
                connection,
                event_id=event_id,
                playbook_key=playbook_key,
                version=version,
                playbook_version_id=playbook_version_id,
                actor=actor,
                event_type=event_type,
                correlation_id=correlation_id,
                row_version_after=row_version_after,
                metadata=metadata,
            )
        except Exception as exc:
            raise PlaybookAuditWriteFailed(
                f"playbook audit insert failed for {event_type.value}"
            ) from exc

    def _append_casework_audit(
        self,
        connection: Connection,
        *,
        event_id: UUID,
        matter_id: UUID,
        actor: str,
        event_type: AuditEventType,
        entity_type: str,
        entity_id: UUID | None,
        correlation_id: UUID | None,
        reason: str | None,
        source_channel: str,
        metadata: dict[str, object],
    ) -> None:
        try:
            self._casework.append_audit_event(
                connection,
                event_id=event_id,
                matter_id=matter_id,
                actor=actor,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=correlation_id,
                reason=reason,
                source_channel=source_channel,
                metadata=metadata,
            )
        except Exception as exc:
            raise PlaybookAuditWriteFailed(
                f"casework audit insert failed for {event_type.value}"
            ) from exc

    @staticmethod
    def _maybe_inject(failure_inject: str | None, point: str) -> None:
        """Raise when ``failure_inject`` matches. Test-only; never set in production."""

        if failure_inject is not None and failure_inject == point:
            raise RuntimeError(f"test-only failure injection: {point}")


__all__ = [
    "PlaybookService",
]

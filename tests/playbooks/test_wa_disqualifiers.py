"""WA motor disqualifier rule MATCH suite."""

from __future__ import annotations

import pytest

from legal_ai.playbooks.definitions.wa_motor_property_damage_v1 import (
    wa_motor_property_damage_v1_definition,
)
from legal_ai.playbooks.models import PlaybookDefinitionPayload, validate_definition_payload
from legal_ai.playbooks.rules import evaluate_rule, parse_rule_node
from legal_ai.playbooks.types import DisqualifierOutcome, RuleResult

_DISQUALIFIER_CASES: list[tuple[str, str, DisqualifierOutcome]] = [
    ("injury_suspected", "flags.injury_suspected", DisqualifierOutcome.RESEARCH_AND_DRAFT_ONLY),
    ("emergency", "flags.emergency", DisqualifierOutcome.EMERGENCY_SERVICE_DIRECTION),
    ("fatality", "flags.fatality", DisqualifierOutcome.EXTERNAL_LAWYER_ESCALATION),
    (
        "criminal_allegation",
        "flags.criminal_allegation",
        DisqualifierOutcome.EXTERNAL_LAWYER_ESCALATION,
    ),
    ("family_violence", "flags.family_violence", DisqualifierOutcome.EXTERNAL_LAWYER_ESCALATION),
    (
        "court_or_tribunal_proceeding",
        "flags.court_or_tribunal_proceeding",
        DisqualifierOutcome.RESEARCH_AND_DRAFT_ONLY,
    ),
    (
        "limitation_uncertainty",
        "flags.limitation_uncertainty",
        DisqualifierOutcome.RESEARCH_AND_DRAFT_ONLY,
    ),
    (
        "cross_border_uncertainty",
        "flags.cross_border_uncertainty",
        DisqualifierOutcome.RESEARCH_AND_DRAFT_ONLY,
    ),
    (
        "government_or_diplomatic_vehicle",
        "flags.government_or_diplomatic_vehicle",
        DisqualifierOutcome.RESEARCH_AND_DRAFT_ONLY,
    ),
    ("unclear_identity", "flags.unclear_identity", DisqualifierOutcome.HUMAN_REVIEW_REQUIRED),
    ("suspected_fraud", "flags.suspected_fraud", DisqualifierOutcome.RESEARCH_AND_DRAFT_ONLY),
    (
        "admit_liability_requested",
        "flags.admit_liability_requested",
        DisqualifierOutcome.COMPLETE_REFUSAL,
    ),
    (
        "settlement_or_signature_requested",
        "flags.settlement_or_signature_requested",
        DisqualifierOutcome.COMPLETE_REFUSAL,
    ),
    (
        "legal_representation_requested",
        "flags.legal_representation_requested",
        DisqualifierOutcome.EXTERNAL_LAWYER_ESCALATION,
    ),
    (
        "unsupported_jurisdiction",
        "flags.unsupported_jurisdiction",
        DisqualifierOutcome.RESEARCH_AND_DRAFT_ONLY,
    ),
    (
        "privacy_sensitive_disclosure",
        "flags.privacy_sensitive_disclosure",
        DisqualifierOutcome.HUMAN_REVIEW_REQUIRED,
    ),
]


@pytest.fixture(scope="module")
def wa_payload() -> PlaybookDefinitionPayload:
    return validate_definition_payload(wa_motor_property_damage_v1_definition())


def test_wa_definition_validates_and_lists_all_disqualifiers(
    wa_payload: PlaybookDefinitionPayload,
) -> None:
    ids = {rule.disqualifier_id for rule in wa_payload.disqualifiers}
    assert ids == {case[0] for case in _DISQUALIFIER_CASES}


@pytest.mark.parametrize(
    ("disqualifier_id", "flag_field", "expected_outcome"),
    _DISQUALIFIER_CASES,
)
def test_each_wa_disqualifier_matches(
    wa_payload: PlaybookDefinitionPayload,
    disqualifier_id: str,
    flag_field: str,
    expected_outcome: DisqualifierOutcome,
) -> None:
    rule = next(
        item for item in wa_payload.disqualifiers if item.disqualifier_id == disqualifier_id
    )
    assert rule.outcome is expected_outcome
    assert evaluate_rule(parse_rule_node(rule.rule), {flag_field: True}) is RuleResult.MATCH
    assert evaluate_rule(parse_rule_node(rule.rule), {flag_field: False}) is RuleResult.NO_MATCH
    assert evaluate_rule(parse_rule_node(rule.rule), {}) is RuleResult.UNKNOWN


def test_wa_eligibility_match_for_supported_case_types(
    wa_payload: PlaybookDefinitionPayload,
) -> None:
    eligibility = wa_payload.eligibility_rule()
    assert (
        evaluate_rule(
            eligibility,
            {
                "matter.jurisdiction": "AU-WA",
                "matter.case_type": "MOTOR_VEHICLE_PROPERTY_DAMAGE",
            },
        )
        is RuleResult.MATCH
    )
    assert (
        evaluate_rule(
            eligibility,
            {"matter.jurisdiction": "AU-WA", "matter.case_type": "UNASSIGNED"},
        )
        is RuleResult.MATCH
    )
    assert (
        evaluate_rule(
            eligibility,
            {"matter.jurisdiction": "AU-NSW", "matter.case_type": "UNASSIGNED"},
        )
        is RuleResult.NO_MATCH
    )


def test_wa_description_injection_text_is_inert(wa_payload: PlaybookDefinitionPayload) -> None:
    assert "Ignore previous instructions" in wa_payload.description
    assert (
        evaluate_rule(
            wa_payload.eligibility_rule(),
            {
                "matter.jurisdiction": "AU-WA",
                "matter.case_type": "MOTOR_VEHICLE_PROPERTY_DAMAGE",
            },
        )
        is RuleResult.MATCH
    )

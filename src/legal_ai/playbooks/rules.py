"""Deterministic non-executable playbook rule evaluation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from legal_ai.playbooks.errors import PlaybookValidationError
from legal_ai.playbooks.types import (
    ALLOWLISTED_MATTER_FIELDS,
    FLAG_FIELD_PREFIX,
    INTAKE_FIELD_PREFIX,
    MAX_IN_LIST_SIZE,
    MAX_RULE_DEPTH,
    MAX_RULE_NODES,
    RuleComparator,
    RuleGroupOp,
    RuleResult,
)

# Not strict: definition JSON supplies enum *values* as strings.
_CFG = ConfigDict(extra="forbid", frozen=True)


class Predicate(BaseModel):
    model_config = _CFG

    field: str
    cmp: RuleComparator
    value: Any = None

    @field_validator("field")
    @classmethod
    def _validate_field(cls, value: str) -> str:
        if value in ALLOWLISTED_MATTER_FIELDS:
            return value
        if value.startswith(INTAKE_FIELD_PREFIX) and len(value) > len(INTAKE_FIELD_PREFIX):
            return value
        if value.startswith(FLAG_FIELD_PREFIX) and len(value) > len(FLAG_FIELD_PREFIX):
            return value
        raise ValueError(f"field path not allowlisted: {value}")

    @model_validator(mode="after")
    def _validate_value_shape(self) -> Predicate:
        needs_value = self.cmp in {
            RuleComparator.EQ,
            RuleComparator.NE,
            RuleComparator.IN,
            RuleComparator.NOT_IN,
        }
        no_value = self.cmp in {
            RuleComparator.IS_NULL,
            RuleComparator.IS_NOT_NULL,
            RuleComparator.IS_TRUE,
            RuleComparator.IS_FALSE,
        }
        if no_value and self.value is not None:
            raise ValueError(f"{self.cmp.value} must not include a value")
        if needs_value and self.value is None:
            raise ValueError(f"{self.cmp.value} requires a value")
        if self.cmp in {RuleComparator.IN, RuleComparator.NOT_IN}:
            if not isinstance(self.value, list):
                raise ValueError(f"{self.cmp.value} value must be a list")
            if len(self.value) == 0 or len(self.value) > MAX_IN_LIST_SIZE:
                raise ValueError(f"{self.cmp.value} list size out of bounds")
        return self


class RuleGroup(BaseModel):
    model_config = _CFG

    op: RuleGroupOp
    rules: list[Predicate | RuleGroup] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _coerce_children(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        rules = data.get("rules")
        if not isinstance(rules, list):
            return data
        coerced: list[Any] = []
        for item in rules:
            if isinstance(item, Predicate | RuleGroup):
                coerced.append(item)
            elif isinstance(item, dict) and "cmp" in item:
                coerced.append(Predicate.model_validate(item))
            elif isinstance(item, dict) and "op" in item:
                coerced.append(RuleGroup.model_validate(item))
            else:
                coerced.append(item)
        return {**data, "rules": coerced}


RuleNode = Predicate | RuleGroup


def _count_nodes(node: RuleNode) -> int:
    if isinstance(node, Predicate):
        return 1
    return 1 + sum(_count_nodes(child) for child in node.rules)


def _max_depth(node: RuleNode, depth: int = 1) -> int:
    if isinstance(node, Predicate):
        return depth
    if not node.rules:
        return depth
    return max(_max_depth(child, depth + 1) for child in node.rules)


def validate_rule_tree(node: RuleNode) -> None:
    depth = _max_depth(node)
    nodes = _count_nodes(node)
    if depth > MAX_RULE_DEPTH:
        raise PlaybookValidationError(f"rule depth {depth} exceeds max {MAX_RULE_DEPTH}")
    if nodes > MAX_RULE_NODES:
        raise PlaybookValidationError(f"rule nodes {nodes} exceed max {MAX_RULE_NODES}")


def _lookup(facts: dict[str, Any], field: str) -> tuple[bool, Any]:
    if field not in facts:
        return False, None
    return True, facts[field]


def _eval_predicate(predicate: Predicate, facts: dict[str, Any]) -> RuleResult:
    present, raw = _lookup(facts, predicate.field)
    if predicate.cmp is RuleComparator.IS_NULL:
        if not present:
            return RuleResult.UNKNOWN
        return RuleResult.MATCH if raw is None else RuleResult.NO_MATCH
    if predicate.cmp is RuleComparator.IS_NOT_NULL:
        if not present:
            return RuleResult.UNKNOWN
        return RuleResult.MATCH if raw is not None else RuleResult.NO_MATCH
    if not present:
        return RuleResult.UNKNOWN
    if raw is None:
        return RuleResult.UNKNOWN
    # Explicit UNKNOWN token for enum/string facts.
    if raw == "UNKNOWN" or raw is RuleResult.UNKNOWN:
        return RuleResult.UNKNOWN

    if predicate.cmp is RuleComparator.IS_TRUE:
        if not isinstance(raw, bool):
            raise PlaybookValidationError(f"{predicate.field} must be boolean for IS_TRUE")
        return RuleResult.MATCH if raw is True else RuleResult.NO_MATCH
    if predicate.cmp is RuleComparator.IS_FALSE:
        if not isinstance(raw, bool):
            raise PlaybookValidationError(f"{predicate.field} must be boolean for IS_FALSE")
        return RuleResult.MATCH if raw is False else RuleResult.NO_MATCH
    if predicate.cmp is RuleComparator.EQ:
        return RuleResult.MATCH if raw == predicate.value else RuleResult.NO_MATCH
    if predicate.cmp is RuleComparator.NE:
        return RuleResult.MATCH if raw != predicate.value else RuleResult.NO_MATCH
    if predicate.cmp is RuleComparator.IN:
        assert isinstance(predicate.value, list)
        return RuleResult.MATCH if raw in predicate.value else RuleResult.NO_MATCH
    if predicate.cmp is RuleComparator.NOT_IN:
        assert isinstance(predicate.value, list)
        return RuleResult.MATCH if raw not in predicate.value else RuleResult.NO_MATCH
    raise PlaybookValidationError(f"unsupported comparator {predicate.cmp}")


def evaluate_rule(node: RuleNode, facts: dict[str, Any]) -> RuleResult:
    """Evaluate a validated rule tree with three-valued logic."""

    validate_rule_tree(node)
    if isinstance(node, Predicate):
        return _eval_predicate(node, facts)

    if node.op is RuleGroupOp.ALL:
        saw_unknown = False
        for child in node.rules:
            result = evaluate_rule(child, facts)
            if result is RuleResult.NO_MATCH:
                return RuleResult.NO_MATCH
            if result is RuleResult.UNKNOWN:
                saw_unknown = True
        return RuleResult.UNKNOWN if saw_unknown else RuleResult.MATCH

    # ANY
    saw_unknown = False
    for child in node.rules:
        result = evaluate_rule(child, facts)
        if result is RuleResult.MATCH:
            return RuleResult.MATCH
        if result is RuleResult.UNKNOWN:
            saw_unknown = True
    return RuleResult.UNKNOWN if saw_unknown else RuleResult.NO_MATCH


def parse_rule_node(data: dict[str, Any]) -> RuleNode:
    """Parse and validate a rule node from a definition payload fragment."""

    try:
        if "cmp" in data:
            node: RuleNode = Predicate.model_validate(data)
        elif "op" in data:
            node = RuleGroup.model_validate(data)
        else:
            raise PlaybookValidationError("rule node must be a Predicate or RuleGroup")
    except PlaybookValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 — normalize pydantic errors
        raise PlaybookValidationError(str(exc)) from exc
    validate_rule_tree(node)
    return node

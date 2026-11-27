from collections.abc import Sequence
from dataclasses import dataclass, field

from rastro.detection.name_rules import (
    category_sensitivity,
    matching_name_rules,
    suppression_context,
)
from rastro.detection.normalize import normalize_name
from rastro.detection.value_patterns import matching_value_patterns
from rastro.models import Category, Detector, SensitiveSubcategory, Sensitivity, ValueKind

_SUPPRESSIBLE_CATEGORIES = {Category.IDENTIFIER, Category.CONTACT}


@dataclass(frozen=True)
class Detection:
    category: Category
    subcategory: SensitiveSubcategory | None
    sensitivity: Sensitivity
    confidence: float
    detector: Detector
    rule_id: str
    kind: ValueKind | None
    raw_evidence: str = field(repr=False)


@dataclass
class SuppressionRecord:
    rule_id: str
    context: str
    detector: Detector


@dataclass
class ColumnDetection:
    detections: list[Detection]
    suppressed: list[SuppressionRecord]


def detect_column(*, table: str, column: str, samples: Sequence[str | None]) -> ColumnDetection:
    table_tokens = normalize_name(table)
    column_tokens = normalize_name(column)
    name_matches = list(matching_name_rules(column_tokens))
    context = suppression_context(table_tokens, column_tokens, has_personal_name=bool(name_matches))
    result = ColumnDetection(detections=[], suppressed=[])

    for rule, evidence in name_matches:
        rule_context = context
        if rule_context is None and rule.unless:
            token = next(
                (token for token in (*column_tokens, *table_tokens) if token in rule.unless), None
            )
            if token is not None:
                rule_context = f"unless:{token}"
        if rule_context is not None and rule.category in _SUPPRESSIBLE_CATEGORIES:
            result.suppressed.append(SuppressionRecord(rule.rule_id, rule_context, Detector.NAME))
            continue
        result.detections.append(Detection(
            category=rule.category,
            subcategory=rule.subcategory,
            sensitivity=category_sensitivity(rule.category),
            confidence=rule.confidence,
            detector=Detector.NAME,
            rule_id=rule.rule_id,
            kind=None,
            raw_evidence=evidence,
        ))

    for kind, category, confidence, evidence in matching_value_patterns(samples):
        rule_id = f"pattern.{kind.value}"
        if context is not None and category in _SUPPRESSIBLE_CATEGORIES:
            result.suppressed.append(SuppressionRecord(rule_id, context, Detector.PATTERN))
            continue
        result.detections.append(Detection(
            category=category,
            subcategory=None,
            sensitivity=category_sensitivity(category),
            confidence=confidence,
            detector=Detector.PATTERN,
            rule_id=rule_id,
            kind=kind,
            raw_evidence=evidence,
        ))

    return result

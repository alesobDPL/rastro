from collections.abc import Sequence
from dataclasses import dataclass

from rastro.detection.detect import Detection
from rastro.detection.name_rules import has_free_text_token
from rastro.detection.normalize import normalize_name
from rastro.detection.thresholds import CONFIDENCE_THRESHOLD, FREE_TEXT_MIN_AVG_LENGTH
from rastro.detection.value_patterns import non_null_values
from rastro.models import Category, Status


@dataclass
class ColumnVerdict:
    status: Status
    sensitive: bool
    categories: list[Category]


def _has_long_text(samples: Sequence[str | None]) -> bool:
    values = [value.strip() for value in non_null_values(samples)]
    return (
        bool(values)
        and sum(map(len, values)) / len(values) >= FREE_TEXT_MIN_AVG_LENGTH
        and any(len(value.split()) > 1 for value in values)
    )


def classify_column(
    detections: Sequence[Detection],
    *,
    column: str,
    is_text: bool,
    samples: Sequence[str | None],
) -> ColumnVerdict:
    qualifying = {
        finding.category for finding in detections if finding.confidence >= CONFIDENCE_THRESHOLD
    }
    categories = [category for category in Category if category in qualifying]
    if categories:
        sensitive = bool(qualifying & {Category.SENSITIVE, Category.MINORS})
        return ColumnVerdict(Status.PERSONAL, sensitive, categories)
    if is_text and (has_free_text_token(normalize_name(column)) or _has_long_text(samples)):
        return ColumnVerdict(Status.AMBIGUOUS, False, [])
    return ColumnVerdict(Status.NOT_PERSONAL, False, [])

from collections.abc import Iterator, Sequence

from rastro.detection.thresholds import MIN_NON_NULL_VALUES, PATTERN_MIN_MATCH_RATIO
from rastro.detection.validators import is_cl_phone, is_email, is_plate, is_valid_rut, luhn_ok
from rastro.models import Category, ValueKind


def _is_card(value: str) -> bool:
    digits = value.strip()
    return 13 <= len(digits) <= 19 and luhn_ok(digits)


_PATTERNS = (
    (ValueKind.RUT, Category.IDENTIFIER, is_valid_rut),
    (ValueKind.EMAIL, Category.CONTACT, is_email),
    (ValueKind.PHONE, Category.CONTACT, is_cl_phone),
    (ValueKind.PLATE, Category.IDENTIFIER, is_plate),
    (ValueKind.CARD, Category.FINANCIAL, _is_card),
)


def non_null_values(samples: Sequence[str | None]) -> list[str]:
    return [value for value in samples if value is not None and value.strip()]


def matching_value_patterns(
    samples: Sequence[str | None],
) -> Iterator[tuple[ValueKind, Category, float, str]]:
    values = non_null_values(samples)
    if len(values) < MIN_NON_NULL_VALUES:
        return
    for kind, category, validator in _PATTERNS:
        matches = [value for value in values if validator(value)]
        confidence = len(matches) / len(values)
        if matches and confidence >= PATTERN_MIN_MATCH_RATIO:
            yield kind, category, confidence, matches[0]

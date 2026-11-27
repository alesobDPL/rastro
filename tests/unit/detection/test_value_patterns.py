import pytest

from rastro.detection.detect import detect_column
from rastro.models import Category, Detector, ValueKind

RUTS = ["12.345.678-5", "12345678-5", "10.000.013-K", "10.000.004-0"]


@pytest.mark.parametrize(
    "samples",
    [[], RUTS, RUTS + [None, "", " \t"], RUTS[:3] + ["abc"] * 3, [None, ""] * 5],
)
def test_empty_small_or_low_match_sample(samples: list[str | None]) -> None:
    result = detect_column(table="personas", column="valor", samples=samples)
    assert result.detections == []


def test_pattern_confidence_ignores_null_and_blank_values() -> None:
    samples = [*RUTS, "abc", "def", None, "", " \t"]
    (finding,) = detect_column(table="personas", column="valor", samples=samples).detections
    assert finding.rule_id == "pattern.rut"
    assert finding.detector is Detector.PATTERN
    assert finding.category is Category.IDENTIFIER
    assert finding.confidence == pytest.approx(4 / 6)
    assert finding.kind is ValueKind.RUT
    assert finding.raw_evidence in RUTS


@pytest.mark.parametrize(
    ("value", "kind", "category"),
    [
        ("987654321", ValueKind.PHONE, Category.CONTACT),
        ("56987654321", ValueKind.PHONE, Category.CONTACT),
        ("4111111111111111", ValueKind.CARD, Category.FINANCIAL),
        ("BBCD12", ValueKind.PLATE, Category.IDENTIFIER),
        ("ana@x.cl", ValueKind.EMAIL, Category.CONTACT),
    ],
)
def test_patterns_include_the_threshold_and_preserve_raw_evidence(
    value: str, kind: ValueKind, category: Category,
) -> None:
    sample_value = f" {value} "
    samples = [sample_value] * 3 + ["abc"] * 2
    (finding,) = detect_column(table="personas", column="valor", samples=samples).detections
    assert finding.kind is kind
    assert finding.rule_id == f"pattern.{kind.value}"
    assert finding.category is category
    assert finding.confidence == 3 / 5
    assert finding.raw_evidence == sample_value
    assert sample_value not in repr(finding)

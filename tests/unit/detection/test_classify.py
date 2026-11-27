import pytest

from rastro.detection.classify import classify_column
from rastro.detection.detect import Detection
from rastro.detection.thresholds import CONFIDENCE_THRESHOLD
from rastro.models import Category, Detector, Sensitivity, Status


def make_detection(category: Category, confidence: float = CONFIDENCE_THRESHOLD) -> Detection:
    return Detection(
        category, None, Sensitivity.HIGH, confidence, Detector.NAME, "name.test", None, "dato",
    )


def test_personal_at_threshold() -> None:
    verdict = classify_column(
        [make_detection(Category.CONTACT)], column="observaciones", is_text=True, samples=[],
    )
    assert verdict.status is Status.PERSONAL
    assert not verdict.sensitive
    assert verdict.categories == [Category.CONTACT]


def test_categories_are_unique_and_in_enum_order() -> None:
    detections = [
        make_detection(Category.MINORS),
        make_detection(Category.CONTACT),
        make_detection(Category.IDENTIFIER),
        make_detection(Category.CONTACT),
        make_detection(Category.SENSITIVE, confidence=0.55),
    ]
    verdict = classify_column(detections, column="valor", is_text=False, samples=[])
    assert verdict.status is Status.PERSONAL
    assert verdict.sensitive
    assert verdict.categories == [Category.IDENTIFIER, Category.CONTACT, Category.MINORS]


@pytest.mark.parametrize("column", ["observaciones", "obs", "detalle", "notes", "comment"])
def test_ambiguous_free_text_name(column: str) -> None:
    verdict = classify_column([], column=column, is_text=True, samples=[])
    assert verdict.status is Status.AMBIGUOUS
    assert not verdict.sensitive
    assert verdict.categories == []


def test_ambiguous_text_with_spaces_and_sufficient_average_length() -> None:
    verdict = classify_column(
        [], column="valor", is_text=True, samples=["a" * 9 + " " + "b" * 10, None, " \t"],
    )
    assert verdict.status is Status.AMBIGUOUS


@pytest.mark.parametrize(
    ("column", "is_text", "samples"),
    [("observaciones", False, []), ("valor", True, []), ("valor", True, ["x" * 30])],
)
def test_not_personal(column: str, is_text: bool, samples: list[str]) -> None:
    verdict = classify_column(
        [make_detection(Category.MINORS, confidence=0.55)],
        column=column,
        is_text=is_text,
        samples=samples,
    )
    assert verdict.status is Status.NOT_PERSONAL
    assert not verdict.sensitive
    assert verdict.categories == []

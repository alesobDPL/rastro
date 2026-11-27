import pytest

from rastro.detection.detect import detect_column
from rastro.models import Category, Detector


@pytest.mark.parametrize(
    ("table", "column", "context"),
    [
        ("proveedores", "rut", "proveedor"),
        ("personas", "tipo_email", "tipo"),
        ("personas", "email_id", "suffix:id"),
        ("personas", "empresa_email", "empresa"),
        ("personas", "email_codigo", "suffix:codigo"),
    ],
)
def test_context_suppression(table: str, column: str, context: str) -> None:
    result = detect_column(table=table, column=column, samples=[])
    assert result.detections == []
    (suppression,) = result.suppressed
    assert suppression.rule_id.startswith("name.")
    assert suppression.detector is Detector.NAME
    assert context in suppression.context


def test_organization_context_suppresses_value_pattern() -> None:
    result = detect_column(table="empresas", column="contacto", samples=["ana@x.cl"] * 6)
    assert result.detections == []
    assert {record.detector for record in result.suppressed} == {Detector.NAME, Detector.PATTERN}
    assert any(record.rule_id == "pattern.email" for record in result.suppressed)
    assert all("empresa" in record.context for record in result.suppressed)


@pytest.mark.parametrize(
    ("column", "category"),
    [
        ("diagnostico", Category.SENSITIVE),
        ("tipo_alumno_id", Category.MINORS),
        ("direccion_id", Category.LOCATION),
        ("sueldo_id", Category.FINANCIAL),
    ],
)
def test_context_preserves_other_categories(column: str, category: Category) -> None:
    result = detect_column(table="tickets_soporte", column=column, samples=[])
    assert any(finding.category is category for finding in result.detections)
    assert result.suppressed == []

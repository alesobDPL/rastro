import pytest

from rastro.detection.detect import detect_column
from rastro.models import Category, Detector, SensitiveSubcategory, Sensitivity


def test_rut_name_rule() -> None:
    result = detect_column(table="personas", column="rut", samples=[])
    (finding,) = result.detections
    assert finding.category is Category.IDENTIFIER
    assert finding.sensitivity is Sensitivity.MEDIUM
    assert finding.confidence == 0.9
    assert finding.detector is Detector.NAME
    assert finding.rule_id.startswith("name.")
    assert finding.kind is None
    assert finding.raw_evidence == "rut"
    assert result.suppressed == []


def test_phone_name_rule() -> None:
    (finding,) = detect_column(table="personas", column="fono_contacto", samples=[]).detections
    assert finding.category is Category.CONTACT
    assert finding.sensitivity is Sensitivity.LOW
    assert finding.confidence == 0.8
    assert finding.raw_evidence == "fono"


@pytest.mark.parametrize("column", ["rut_dv", "digito_verificador"])
def test_rut_check_digit_name_rule(column: str) -> None:
    result = detect_column(table="personas", column=column, samples=[])
    assert any(finding.category is Category.IDENTIFIER for finding in result.detections)


def test_health_name_rule() -> None:
    (finding,) = detect_column(table="personas", column="diagnostico", samples=[]).detections
    assert finding.category is Category.SENSITIVE
    assert finding.subcategory is SensitiveSubcategory.HEALTH
    assert finding.sensitivity is Sensitivity.HIGH


def test_minor_name_rule() -> None:
    result = detect_column(table="personas", column="nombre_alumno", samples=[])
    assert any(finding.category is Category.MINORS for finding in result.detections)


@pytest.mark.parametrize(
    ("column", "evidence", "category"),
    [
        ("email_address", "email address", Category.CONTACT),
        ("gender_identity", "gender identity", Category.SENSITIVE),
    ],
)
def test_compound_name_uses_its_specific_category(
    column: str, evidence: str, category: Category,
) -> None:
    (finding,) = detect_column(table="people", column=column, samples=[]).detections
    assert finding.category is category
    assert finding.raw_evidence == evidence


@pytest.mark.parametrize(
    ("names", "category"),
    [
        (("identificacion_nacional", "national_id_number"), Category.IDENTIFIER),
        (("apellido_paterno", "last_name"), Category.IDENTIFIER),
        (("fecha_nacimiento", "date_of_birth"), Category.IDENTIFIER),
        (("edad", "age", "sexo", "gender"), Category.IDENTIFIER),
        (("correo_electronico", "email"), Category.CONTACT),
        (("telefono", "telephone"), Category.CONTACT),
        (("direccion", "address", "comuna", "municipality", "region"), Category.LOCATION),
        (("coordenadas", "coordinates"), Category.LOCATION),
        (("tarjeta", "credit_card", "cuenta_bancaria", "bank_account"), Category.FINANCIAL),
        (("sueldo", "salary"), Category.FINANCIAL),
        (("licencia_medica", "medical_leave", "pet_allergy"), Category.SENSITIVE),
        (("huella_dactilar", "fingerprint", "origen_etnico", "ethnicity"), Category.SENSITIVE),
        (("religion", "beliefs", "orientacion_sexual", "gender_identity"), Category.SENSITIVE),
        (("afiliacion_politica", "political_affiliation"), Category.SENSITIVE),
        (("afiliacion_sindical", "trade_union_membership"), Category.SENSITIVE),
        (("hijo", "child", "apoderado", "guardian", "student_birth_date"), Category.MINORS),
    ],
)
def test_dictionary_coverage(names: tuple[str, ...], category: Category) -> None:
    for name in names:
        result = detect_column(table="personas", column=name, samples=[])
        assert any(finding.category is category for finding in result.detections), name


def test_unrelated_name_has_no_findings() -> None:
    result = detect_column(table="personas", column="cantidad", samples=[])
    assert result.detections == []
    assert result.suppressed == []

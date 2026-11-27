import pytest

from rastro.detection.classify import classify_column
from rastro.detection.detect import detect_column
from rastro.models import Category, Detector, SensitiveSubcategory, Status

_EMAILS = [f"persona{index}@example.cl" for index in range(5)]


@pytest.mark.parametrize(
    ("phrase", "category"),
    [
        ("titular", Category.IDENTIFIER),
        ("responsable", Category.IDENTIFIER),
        ("recibido por", Category.IDENTIFIER),
        ("received by", Category.IDENTIFIER),
        ("monto", Category.FINANCIAL),
        ("reembolso", Category.FINANCIAL),
        ("reembolsado", Category.FINANCIAL),
        ("pagado", Category.FINANCIAL),
        ("cobrado", Category.FINANCIAL),
        ("medio de pago", Category.FINANCIAL),
        ("payment method", Category.FINANCIAL),
        ("refund amount", Category.FINANCIAL),
        ("anestesico", Category.SENSITIVE),
        ("clinico", Category.SENSITIVE),
        ("terapia", Category.SENSITIVE),
        ("procedimiento quirurgico", Category.SENSITIVE),
        ("alta medica", Category.SENSITIVE),
        ("clinical finding", Category.SENSITIVE),
        ("placa vehiculo", Category.IDENTIFIER),
        ("placa del vehiculo", Category.IDENTIFIER),
    ],
)
def test_tuned_name_vocabulary(phrase: str, category: Category) -> None:
    column = f"valor_{phrase.replace(' ', '_')}_declarado"
    result = detect_column(table="fichas_declaradas", column=column, samples=[])
    (finding,) = result.detections
    assert finding.category is category
    assert finding.detector is Detector.NAME
    if category is Category.SENSITIVE:
        assert finding.subcategory is SensitiveSubcategory.HEALTH
    assert result.suppressed == []


@pytest.mark.parametrize(
    "column",
    ["valor_prometido", "folio_transferencia", "agenda_clinica", "placa_conmemorativa"],
)
def test_unrelated_names_remain_undetected(column: str) -> None:
    assert detect_column(table="formularios", column=column, samples=[]).detections == []


@pytest.mark.parametrize(
    ("column", "context"),
    [
        ("rut_entidad_juridica", "juridica"),
        ("rut_gestion_aduanera", "aduanera"),
        ("telefono_oficina_central", "central"),
        ("patente_flota_arrendada", "flota"),
        ("patente_vehiculo_corporativo", "corporativo"),
        ("email_difusion_campana", "campana"),
        ("correo_boletin_transaccional", "transaccional"),
    ],
)
def test_nonpersonal_context_is_recorded(column: str, context: str) -> None:
    result = detect_column(table="formularios", column=column, samples=[])
    assert result.detections == []
    (record,) = result.suppressed
    assert record.context == context
    assert record.detector is Detector.NAME


@pytest.mark.parametrize("animal", ["animal", "mascota", "pet"])
@pytest.mark.parametrize("field", ["nombre", "nacimiento", "edad", "sexo"])
def test_animal_demographics_are_not_identifiers(animal: str, field: str) -> None:
    result = detect_column(table="fichas", column=f"{field}_de_{animal}", samples=[])
    assert result.detections == []
    (record,) = result.suppressed
    assert record.context == f"unless:{animal}"


def test_animal_health_survives_name_suppression() -> None:
    result = detect_column(table="fichas_mascota", column="nombre_del_diagnostico", samples=[])
    (finding,) = result.detections
    assert (finding.category, finding.subcategory) == (
        Category.SENSITIVE, SensitiveSubcategory.HEALTH,
    )
    assert [record.context for record in result.suppressed] == ["unless:mascota"]


@pytest.mark.parametrize(
    ("column", "category"),
    [("nombre_declarado", Category.IDENTIFIER), ("correo_alterno", Category.CONTACT)],
)
def test_neutral_table_preserves_person(column: str, category: Category) -> None:
    result = detect_column(table="inscripciones", column=column, samples=[])
    assert [finding.category for finding in result.detections] == [category]
    assert result.suppressed == []


@pytest.mark.parametrize(
    "role",
    [
        "agente",
        "ejecutivo",
        "titular",
        "responsable",
        "retirante",
        "particular",
        "agent",
        "holder",
        "driver",
        "customer",
    ],
)
def test_role_restores_name_and_pattern_in_organization_table(role: str) -> None:
    # El correo y el rol se prueban por separado de la regla de identificadores por rol.
    result = detect_column(table="agenda_sucursal", column=f"email_del_{role}", samples=_EMAILS)
    assert {finding.detector for finding in result.detections
            if finding.category is Category.CONTACT} == {Detector.NAME, Detector.PATTERN}
    assert result.suppressed == []


@pytest.mark.parametrize(
    ("column", "context"),
    [
        ("email_alterno", "sucursal"),
        ("email_agente_empresa", "empresa"),
        ("email_agente_id", "suffix:id"),
        ("tipo_email_agente", "tipo"),
    ],
)
def test_role_keeps_other_suppressions(column: str, context: str) -> None:
    result = detect_column(table="agenda_sucursal", column=column, samples=_EMAILS)
    assert result.detections == []
    assert {record.detector for record in result.suppressed} == {Detector.NAME, Detector.PATTERN}
    assert {record.context for record in result.suppressed} == {context}


def test_role_does_not_override_rule_exception() -> None:
    result = detect_column(table="agenda_sucursal", column="nombre_mascota_agente", samples=[])
    assert result.detections == []
    assert [record.context for record in result.suppressed] == ["unless:mascota"]


@pytest.mark.parametrize(
    "phrase",
    [
        "cirugia mayor",
        "hospitalizacion clinica",
        "receta medica",
        "examen de laboratorio",
        "registro de vacunacion",
        "surgery",
        "clinical rehabilitation",
    ],
)
def test_clinical_event_supplies_health_evidence(phrase: str) -> None:
    column = "intervalo_previsto"
    table = f"bitacora_{phrase.replace(' ', '_')}_local"
    result = detect_column(table=table, column=column, samples=[])
    (finding,) = result.detections
    assert finding.category is Category.SENSITIVE
    assert finding.subcategory is SensitiveSubcategory.HEALTH
    assert finding.detector is Detector.NAME
    assert finding.kind is None
    assert finding.rule_id.startswith("name.")
    assert finding.raw_evidence == phrase
    verdict = classify_column(result.detections, column=column, is_text=False, samples=[])
    assert verdict.status is Status.PERSONAL
    assert verdict.sensitive is True


@pytest.mark.parametrize(
    "column",
    [
        "sesion_id",
        "clave_interno",
        "codigo_interno",
        "folio_interno",
        "serie_interno",
        "lote_interno",
        "version_interno",
        "creado_interno",
        "actualizado_interno",
        "created_interno",
        "updated_interno",
        "audit_interno",
    ],
)
def test_table_health_excludes_technical_columns(column: str) -> None:
    assert detect_column(table="agenda_cirugia_mayor", column=column, samples=[]).detections == []


@pytest.mark.parametrize(
    "table",
    ["agenda_empresa_cirugia_mayor", "agenda_turnos", "agenda_clinica", "agenda_laboratorio"],
)
def test_table_health_requires_unambiguous_event(table: str) -> None:
    assert detect_column(table=table, column="intervalo_previsto", samples=[]).detections == []


def test_table_health_preserves_existing_name_finding() -> None:
    result = detect_column(table="agenda_cirugia_mayor", column="telefono_alterno", samples=[])
    assert [finding.category for finding in result.detections] == [Category.CONTACT]


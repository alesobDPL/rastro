import csv
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID

from faker import Faker

from rastro.models import Category, SensitiveSubcategory

DEFAULT_SEED = 21719
_ROWS_PER_TABLE = 120


@dataclass(frozen=True)
class Label:
    personal: bool
    sensitive: bool
    category: Category | None
    note: str


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    sql_type: str
    label: Label


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: list[ColumnSpec]
    rows: list[tuple]


@dataclass(frozen=True)
class SchemaSpec:
    name: str
    split: Literal["dev", "holdout"]
    tables: list[TableSpec]


@dataclass(frozen=True)
class Dataset:
    schemas: list[SchemaSpec]

    def iter_values(self) -> Iterator[str]:
        for schema in self.schemas:
            for table in schema.tables:
                for row in table.rows:
                    for value in row:
                        if value is not None:
                            yield str(value)


_PLAIN = Label(False, False, None, "")
_IDENTIFIER = Label(True, False, Category.IDENTIFIER, "")
_CONTACT = Label(True, False, Category.CONTACT, "")
_LOCATION = Label(True, False, Category.LOCATION, "")
_FINANCIAL = Label(True, False, Category.FINANCIAL, "")
_HEALTH = Label(True, True, Category.SENSITIVE, SensitiveSubcategory.HEALTH.value)
_MINORS = Label(True, True, Category.MINORS, "")

_GeneratedColumn = tuple[ColumnSpec, Callable[[], object]]
_CSV_FIELDS = ("schema", "table", "column", "split", "personal", "sensitive", "category", "note")


def _column(
    name: str, generate: Callable[[], object], label: Label = _PLAIN, sql_type: str = "text"
) -> _GeneratedColumn:
    return ColumnSpec(name, sql_type, label), generate


def _trap(
    name: str,
    generate: Callable[[], object],
    note: str,
    label: Label = _PLAIN,
    sql_type: str = "text",
) -> _GeneratedColumn:
    prefix = "trampa_fn" if label.personal else "trampa_fp"
    return _column(name, generate, replace(label, note=f"{prefix} {note}"), sql_type)


def _text(
    name: str, generate: Callable[[], object], note: str, label: Label = _PLAIN
) -> _GeneratedColumn:
    return _column(name, generate, replace(label, note=f"texto_libre {note}"))


class _Values:
    def __init__(self, fake: Faker) -> None:
        self.fake = fake

    def pick(self, *options: str) -> Callable[[], str]:
        return lambda: self.fake.random_element(options)

    def number(self, low: int, high: int) -> Callable[[], int]:
        return lambda: self.fake.random_int(low, high)

    def code(self, pattern: str) -> Callable[[], str]:
        return lambda: self.fake.bothify(pattern, letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def day(self, first_year: int, last_year: int) -> Callable[[], date]:
        start = date(first_year, 1, 1)
        span = (date(last_year, 12, 31) - start).days
        return lambda: start + timedelta(days=self.fake.random_int(0, span))

    def uuid(self) -> UUID:
        return UUID(self.fake.uuid4())

    def rut(self) -> str:
        return self.fake.rut(6_000_000, 29_999_999)

    def plain_rut(self) -> str:
        return self.rut().replace(".", "")

    def company_rut(self) -> str:
        return self.fake.rut(76_000_000, 79_999_999)

    def invalid_reference(self) -> str:
        body, digit = self.rut().rsplit("-", 1)
        invalid_digit = "1" if digit == "0" else "0"
        return f"{body}-{invalid_digit}"

    def email(self) -> str:
        return f"{self.fake.user_name()}@correo.example"

    def phone(self) -> int:
        return self.fake.random_int(56_900_000_000, 56_999_999_999)

    def company_phone(self) -> str:
        return self.fake.numerify("+56 2 2000 ####")

    def table(self, name: str, *fields: _GeneratedColumn) -> TableSpec:
        columns, generators = zip(
            _column("id", self.uuid, sql_type="uuid"),
            _column("creado_el", self.day(2023, 2025), sql_type="date"),
            *fields,
            strict=True,
        )
        rows = [tuple(generate() for generate in generators) for _ in range(_ROWS_PER_TABLE)]
        return TableSpec(name, list(columns), rows)


def _veterinary(values: _Values) -> SchemaSpec:
    fake = values.fake
    table, pick, code, number = values.table, values.pick, values.code, values.number
    commune = pick("Maipú", "Ñuñoa", "Santiago", "Providencia", "La Florida", "Puente Alto")
    owners = table(
        "tutores",
        _column("documento_tutor", values.rut, _IDENTIFIER),
        _column("nombre_tutor", fake.first_name, _IDENTIFIER),
        _column("apellido_tutor", fake.last_name, _IDENTIFIER),
        _column("celular_tutor", values.phone, _CONTACT, "bigint"),
        _column("correo_tutor", values.email, _CONTACT),
    )
    owner_ids = tuple(row[0] for row in owners.rows)
    rut_parts = [values.plain_rut().split("-") for _ in range(_ROWS_PER_TABLE)]
    rut_bodies = iter(int(body) for body, _ in rut_parts)
    rut_digits = iter(digit for _, digit in rut_parts)
    return SchemaSpec(
        "veterinaria",
        "dev",
        [
            owners,
            table(
                "pacientes",
                _column("tutor_id", lambda: fake.random_element(owner_ids), sql_type="uuid"),
                _column("nombre_animal", pick("Luna", "Roco", "Miga", "Canelo")),
                _column("especie", pick("canino", "felino", "conejo")),
                _column("fecha_nacimiento_animal", values.day(2008, 2024), sql_type="date"),
                _column(
                    "alergia_animal", pick("sin alergia conocida", "pollo", "penicilina"), _HEALTH
                ),
            ),
            table(
                "consultas",
                _trap("llave_ingreso", values.plain_rut, "RUT del tutor", _IDENTIFIER),
                _column("tipo_consulta", pick("control", "urgencia", "primera visita")),
                _column("hallazgo_clinico", pick("dermatitis", "otitis", "sin hallazgos"), _HEALTH),
                _text(
                    "relato_consulta",
                    pick("Paciente felino con diabetes", "Canino con cojera leve"),
                    "salud del animal",
                    _HEALTH,
                ),
                _column("atendido", fake.boolean, sql_type="boolean"),
            ),
            table(
                "hospitalizaciones",
                _column("codigo_jaula", code("J-##")),
                _column("responsable_retiro", fake.name, _IDENTIFIER),
                _column("causa_ingreso", pick("fractura", "neumonía", "deshidratación"), _HEALTH),
                _column("dias_internado", number(1, 10), sql_type="integer"),
                _text(
                    "parte_turno",
                    pick("Sala ventilada al inicio del turno", "Jaulas desinfectadas"),
                    "operación de la sala",
                ),
            ),
            table(
                "vacunaciones",
                _trap("clave_campana", values.email, "correo del tutor", _CONTACT),
                _column(
                    "producto_aplicado", pick("triple felina", "antirrábica", "séxtuple"), _HEALTH
                ),
                _column("lote_vacuna", code("VAC-####")),
                _column("dosis_numero", number(1, 3), sql_type="integer"),
                _column("aplicada_el", values.day(2023, 2025), sql_type="date"),
            ),
            table(
                "laboratorio",
                _column("orden_examen", code("LAB-#####")),
                _column("muestra", pick("sangre", "orina", "hisopado"), _HEALTH),
                _column(
                    "resultado_clinico", pick("anemia leve", "glucosa elevada", "normal"), _HEALTH
                ),
                _column("solicitante_nombre", fake.name, _IDENTIFIER),
                _text(
                    "bitacora_equipo",
                    pick("Centrífuga calibrada", "Reactivos en refrigeración"),
                    "operación del equipo",
                ),
            ),
            table(
                "recetas",
                _column("codigo_receta", code("RX-#####")),
                _column("prescriptor_nombre", fake.name, _IDENTIFIER),
                _column(
                    "medicamento_indicado", pick("insulina", "meloxicam", "amoxicilina"), _HEALTH
                ),
                _column("duracion_dias", number(3, 20), _HEALTH, "integer"),
                _text(
                    "pauta_cuidado",
                    pick("Aplicar insulina con la primera comida", "Vigilar la fiebre"),
                    "tratamiento del animal",
                    _HEALTH,
                ),
            ),
            table(
                "cirugias",
                _column("pabellon", code("P-#")),
                _column("procedimiento", pick("extracción dental", "osteosíntesis"), _HEALTH),
                _column("cirujano_nombre", fake.name, _IDENTIFIER),
                _column("duracion_minutos", number(20, 150), _HEALTH, "integer"),
                _column("riesgo_anestesico", pick("bajo", "moderado", "alto"), _HEALTH),
            ),
            table(
                "urgencias",
                _trap("bandeja_a", values.phone, "celular del tutor", _CONTACT, "bigint"),
                _column("prioridad_clinica", pick("leve", "grave", "crítica"), _HEALTH),
                _column(
                    "motivo_urgencia", pick("intoxicación", "quemaduras", "mordedura"), _HEALTH
                ),
                _column("tutor_nombre", fake.name, _IDENTIFIER),
                _column("tiempo_espera_minutos", number(0, 120), sql_type="integer"),
            ),
            table(
                "rehabilitaciones",
                _column("sesion_numero", number(1, 18), sql_type="integer"),
                _column("terapeuta_nombre", fake.name, _IDENTIFIER),
                _column("terapia_animal", pick("hidroterapia", "movilización pasiva"), _HEALTH),
                _text(
                    "evolucion_sesion",
                    pick("Recuperó apoyo de la pata", "Persiste el dolor de cadera"),
                    "recuperación del animal",
                    _HEALTH,
                ),
                _column("alta_clinica", fake.boolean, _HEALTH, "boolean"),
            ),
            table(
                "visitas_domicilio",
                _column("direccion_visita", fake.street_address, _LOCATION),
                _column("comuna_visita", commune, _LOCATION),
                _column("placa_vehiculo_tutor", code("????##"), _IDENTIFIER),
                _trap("patente_unidad_movil", code("????##"), "vehículo de la clínica"),
                _column("estado_visita", pick("pendiente", "realizada", "reprogramada")),
            ),
            table(
                "consentimientos",
                _column("cuerpo_rut", rut_bodies.__next__, _IDENTIFIER, "integer"),
                _column("digito_rut", rut_digits.__next__, _IDENTIFIER),
                _column("firmante_nombre", fake.name, _IDENTIFIER),
                _column("tipo_consentimiento", pick("anestesia", "hospitalización", "examen")),
                _column("aceptado", fake.boolean, sql_type="boolean"),
            ),
            table(
                "convenios",
                _trap("rut_contraparte_juridica", values.company_rut, "RUT de empresa"),
                _trap("fono_mesa_central", values.company_phone, "teléfono de la empresa"),
                _column("empresa_convenio", fake.company),
                _column("contacto_nombre", fake.name, _IDENTIFIER),
                _column("contacto_correo", values.email, _CONTACT),
            ),
            table(
                "cobros",
                _column("pagador_nombre", fake.name, _IDENTIFIER),
                _column("documento_pagador", values.plain_rut, _IDENTIFIER),
                _column("folio_cobro", code("CB-######")),
                _column("total_cobrado", number(5000, 350000), _FINANCIAL, "integer"),
                _column("medio_pago", pick("efectivo", "tarjeta", "transferencia"), _FINANCIAL),
            ),
            table(
                "traslados",
                _column("conductor_nombre", fake.name, _IDENTIFIER),
                _trap("patente_flota_clinica", code("????##"), "vehículo de la clínica"),
                _column("comuna_retiro", commune, _LOCATION),
                _column("direccion_retiro", fake.street_address, _LOCATION),
                _column("prioridad_traslado", pick("programado", "urgente")),
            ),
            table(
                "seguimiento",
                _trap("token_retorno", fake.name, "nombre del tutor", _IDENTIFIER),
                _column("canal", pick("llamada", "visita", "correo")),
                _column("correo_respuesta", values.email, _CONTACT),
                _text(
                    "novedad_paciente",
                    pick("El felino volvió a comer", "No cede la tos del canino"),
                    "evolución del animal",
                    _HEALTH,
                ),
                _column("requiere_control", fake.boolean, _HEALTH, "boolean"),
            ),
            table(
                "seguridad_visitas",
                _column("visitante_nombre", fake.name, _IDENTIFIER),
                _column("pasaporte_visitante", code("??#######"), _IDENTIFIER),
                _column(
                    "alergia_visitante", pick("polen", "látex", "sin alergia conocida"), _HEALTH
                ),
                _column("sector_autorizado", pick("recepción", "sala de reuniones", "patio")),
                _column("credencial_entregada", fake.boolean, sql_type="boolean"),
            ),
            table(
                "personal_clinico",
                _column("especialista_nombre", fake.name, _IDENTIFIER),
                _column("domicilio_especialista", fake.street_address, _LOCATION),
                _column("sueldo_mensual", number(700000, 3500000), _FINANCIAL, "integer"),
                _column("fecha_nacimiento", values.day(1965, 2002), _IDENTIFIER, "date"),
                _column("especialidad", pick("cardiología", "imagenología", "cirugía")),
            ),
            table(
                "inventario_insumos",
                _trap("rut_proveedor_insumos", values.company_rut, "RUT de empresa"),
                _column("codigo_insumo", code("INS-#####")),
                _column("tipo_insumo", pick("jeringa", "gasa", "guante")),
                _column("existencias", number(0, 450), sql_type="integer"),
                _text(
                    "detalle_bodega",
                    pick("Reponer en estante superior", "Caja abierta para conteo"),
                    "organización de bodega",
                ),
            ),
            table(
                "recepcion_paquetes",
                _trap("folio_ingreso", values.invalid_reference, "folio con DV inválido"),
                _column("recibido_por", fake.name, _IDENTIFIER),
                _column("tipo_paquete", pick("caja", "sobre", "contenedor térmico")),
                _column("cantidad_bultos", number(1, 12), sql_type="integer"),
                _column("entrega_conforme", fake.boolean, sql_type="boolean"),
            ),
        ],
    )


def _ecommerce(values: _Values) -> SchemaSpec:
    fake = values.fake
    table, pick, code, number = values.table, values.pick, values.code, values.number
    commune = pick("Valparaíso", "Viña del Mar", "Quilpué", "Concón", "Santiago", "Quinta Normal")
    customers = table(
        "clientes",
        _column("nombre_cliente", fake.name, _IDENTIFIER),
        _column("rut_cliente", values.plain_rut, _IDENTIFIER),
        _column("correo_cliente", values.email, _CONTACT),
        _column("celular_cliente", values.phone, _CONTACT, "bigint"),
        _column("fecha_nacimiento", values.day(1950, 2005), _IDENTIFIER, "date"),
    )
    customer_ids = tuple(row[0] for row in customers.rows)

    def gift_recipient() -> dict[str, str | int]:
        return {"nombre": fake.name(), "correo": values.email(), "celular": values.phone()}

    return SchemaSpec(
        "ecommerce",
        "dev",
        [
            customers,
            table(
                "pedidos",
                _column("comprador_id", lambda: fake.random_element(customer_ids), sql_type="uuid"),
                _trap("dato_factura", values.rut, "RUT del comprador", _IDENTIFIER),
                _column("total_pagado", number(4900, 990000), _FINANCIAL, "integer"),
                _column("boleta_numero", code("B-######")),
                _column("estado_pedido", pick("pagado", "enviado", "entregado")),
            ),
            table(
                "despachos",
                _column("destinatario_nombre", fake.name, _IDENTIFIER),
                _column("direccion_entrega", fake.street_address, _LOCATION),
                _column("comuna_entrega", commune, _LOCATION),
                _trap(
                    "casilla_azul", values.phone, "teléfono del destinatario", _CONTACT, "bigint"
                ),
                _text(
                    "instrucciones_entrega",
                    pick("Entregar en recepción", "Tocar el timbre lateral"),
                    "instrucciones sin datos personales",
                ),
            ),
            table(
                "pagos",
                _column("titular_tarjeta", fake.name, _IDENTIFIER),
                _trap(
                    "captura_b",
                    lambda: int(fake.credit_card_number(card_type="visa")),
                    "número de tarjeta del comprador",
                    _FINANCIAL,
                    "bigint",
                ),
                _column("autorizacion_pasarela", code("AUT-????####")),
                _column("monto_cargado", number(4900, 990000), _FINANCIAL, "integer"),
                _column("reversado", fake.boolean, sql_type="boolean"),
            ),
            table(
                "devoluciones",
                _column("solicitante_nombre", fake.name, _IDENTIFIER),
                _column("cuenta_reembolso", code("##########"), _FINANCIAL),
                _trap(
                    "bandeja_retorno", values.email, "correo de quien pidió el reembolso", _CONTACT
                ),
                _column("monto_reembolsado", number(4900, 990000), _FINANCIAL, "integer"),
                _text(
                    "detalle_devolucion",
                    pick("Costura abierta en el embalaje", "Faltaba una pieza"),
                    "estado del producto",
                ),
            ),
            table(
                "garantias",
                _column("titular_garantia", fake.name, _IDENTIFIER),
                _trap("documento_x", values.plain_rut, "RUT del titular", _IDENTIFIER),
                _column("serie_producto", code("SER-????####")),
                _column("resolucion", pick("reparación", "reemplazo", "rechazada")),
                _text(
                    "informe_taller",
                    pick("La pantalla no enciende", "Se cambió el cable interno"),
                    "diagnóstico del producto",
                ),
            ),
            table(
                "regalos",
                _column("perfil_destino", gift_recipient, _IDENTIFIER, "jsonb"),
                _column("remitente_nombre", fake.name, _IDENTIFIER),
                _column("direccion_regalo", fake.street_address, _LOCATION),
                _column("comuna_regalo", commune, _LOCATION),
                _text(
                    "dedicatoria",
                    lambda: f"{fake.first_name()}, que tengas un lindo cumpleaños",
                    "incluye el nombre del destinatario",
                    _IDENTIFIER,
                ),
            ),
            table(
                "listas_infantiles",
                _column("nombre_menor", fake.first_name, _MINORS),
                _column("edad_menor", number(4, 16), _MINORS, "integer"),
                _column("talla_menor", pick("XS", "S", "M", "L"), _MINORS),
                _column("responsable_nombre", fake.name, _IDENTIFIER),
                _column("correo_responsable", values.email, _CONTACT),
            ),
            table(
                "talleres_infantiles",
                _trap("casillero_ve", fake.name, "nombre del participante menor", _MINORS),
                _column(
                    "alergia_participante", pick("frutos secos", "lácteos", "ninguna"), _MINORS
                ),
                _column("nombre_apoderado", fake.name, _IDENTIFIER),
                _column("celular_apoderado", values.phone, _CONTACT, "bigint"),
                _column("tema_taller", pick("arcilla", "origami", "acuarela")),
            ),
            table(
                "retiros_sucursal",
                _column("retirante_nombre", fake.name, _IDENTIFIER),
                _column("documento_retiro", values.rut, _IDENTIFIER),
                _column("patente_particular", code("????##"), _IDENTIFIER),
                _column("entregado", fake.boolean, sql_type="boolean"),
                _text(
                    "registro_mesón",
                    pick("Paquete sellado", "Se comprobó el número de bultos"),
                    "estado del paquete",
                ),
            ),
            table(
                "proveedores",
                _trap("rut_distribuidora", values.company_rut, "RUT de empresa"),
                _trap(
                    "telefono_central_distribuidora", values.company_phone, "teléfono de la empresa"
                ),
                _column("razon_social", fake.company),
                _column("ejecutivo_nombre", fake.name, _IDENTIFIER),
                _column("correo_ejecutivo", values.email, _CONTACT),
            ),
            table(
                "transportistas",
                _trap("patente_camion_flotante", code("????##"), "vehículo corporativo"),
                _column("conductor_nombre", fake.name, _IDENTIFIER),
                _column("celular_conductor", values.phone, _CONTACT, "bigint"),
                _column("codigo_ruta", code("RT-###")),
                _column("turno", pick("mañana", "tarde", "noche")),
            ),
            table(
                "catalogo",
                _column("sku", code("SKU-????###")),
                _column("familia_producto", pick("librería", "jardín", "cocina")),
                _column("precio_publico", number(1500, 350000), sql_type="integer"),
                _column("visible", fake.boolean, sql_type="boolean"),
                _text(
                    "ficha_producto",
                    pick("Apto para uso interior", "Lavar antes del primer uso"),
                    "instrucciones del producto",
                ),
            ),
            table(
                "cupones",
                _column("codigo_cupon", code("CUP-????")),
                _column("descuento_porcentaje", number(5, 30), sql_type="integer"),
                _column("valido_desde", values.day(2024, 2025), sql_type="date"),
                _column("redencion_maxima", number(10, 500), sql_type="integer"),
                _trap(
                    "correo_emisor_campana",
                    pick("ofertas@tienda.example", "cupones@tienda.example"),
                    "buzón funcional de la tienda",
                ),
            ),
            table(
                "plantillas_mensajes",
                _trap("codigo_correo_transaccional", code("TPL-####"), "código de plantilla"),
                _column("idioma", pick("es-CL", "en-US")),
                _column("evento", pick("pedido listo", "pago aprobado")),
                _column("version", number(1, 5), sql_type="integer"),
                _text(
                    "cuerpo_plantilla",
                    pick("El pedido está listo para retiro", "El pago fue recibido"),
                    "plantilla sin datos del comprador",
                ),
            ),
            table(
                "consultas_soporte",
                _trap("entrada_auxiliar", values.email, "correo del comprador", _CONTACT),
                _column("agente_nombre", fake.name, _IDENTIFIER),
                _text(
                    "consulta_cliente",
                    lambda: f"Solicito entregar en {fake.street_address()}",
                    "dirección solicitada por el comprador",
                    _LOCATION,
                ),
                _column("canal_contacto", pick("chat", "web", "correo")),
                _column("resuelto", fake.boolean, sql_type="boolean"),
            ),
            table(
                "accesibilidad_entregas",
                _column("receptor_nombre", fake.name, _IDENTIFIER),
                _column("celular_receptor", values.phone, _CONTACT, "bigint"),
                _column("direccion_receptor", fake.street_address, _LOCATION),
                _text(
                    "solicitud_asistencia",
                    pick("Usuario de silla de ruedas", "Cliente con baja visión"),
                    "salud del receptor",
                    _HEALTH,
                ),
                _column("preferencia_horaria", pick("mañana", "tarde")),
            ),
            table(
                "resenas",
                _trap("alias_auditoria", fake.name, "nombre del autor", _IDENTIFIER),
                _column("sku_resenado", code("SKU-????###")),
                _column("estrellas", number(1, 5), sql_type="integer"),
                _text(
                    "comentario_producto",
                    pick("El estuche es resistente", "El producto llegó a tiempo"),
                    "opinión sobre el producto",
                ),
                _column("publicada", fake.boolean, sql_type="boolean"),
            ),
            table(
                "ferias",
                _column("visitante_nombre", fake.name, _IDENTIFIER),
                _column("pasaporte_visitante", code("??#######"), _IDENTIFIER),
                _column("correo_visitante", values.email, _CONTACT),
                _column("comuna_visitante", commune, _LOCATION),
                _column("boleto_numero", code("FER-#####")),
            ),
            table(
                "lotes_importacion",
                _trap("referencia_aduana", values.invalid_reference, "folio con DV inválido"),
                _trap("rut_agencia_aduanera", values.company_rut, "RUT de empresa"),
                _column("codigo_contenedor", code("????#######")),
                _column("bultos", number(1, 500), sql_type="integer"),
                _column("puerto_ingreso", pick("San Antonio", "Valparaíso", "Iquique")),
            ),
        ],
    )


def _school(values: _Values) -> SchemaSpec:
    fake = values.fake
    table, pick, code, number = values.table, values.pick, values.code, values.number
    return SchemaSpec(
        "colegio",
        "holdout",
        [
            table(
                "matriculas",
                _column("nombre_estudiante", fake.first_name, _MINORS),
                _column("apellido_estudiante", fake.last_name, _MINORS),
                _trap("casillero_matricula", values.rut, "RUT del estudiante", _MINORS),
                _column("nacimiento_estudiante", values.day(2008, 2019), _MINORS, "date"),
                _column("nivel_lectivo", pick("básica", "media"), _MINORS),
            ),
            table(
                "apoderados",
                _column("nombre_apoderado", fake.name, _IDENTIFIER),
                _column("rut_apoderado", values.plain_rut, _IDENTIFIER),
                _column("comuna_apoderado", pick("Macul", "Peñalolén", "La Reina"), _LOCATION),
                _column("telefono_apoderado", values.phone, _CONTACT, "bigint"),
                _column("correo_apoderado", values.email, _CONTACT),
            ),
            table(
                "fichas_salud",
                _column("estudiante_nombre", fake.name, _MINORS),
                _column(
                    "alergia_escolar", pick("polen", "lácteos", "sin alergia conocida"), _MINORS
                ),
                _column("tratamiento_escolar", pick("salbutamol", "insulina", "ninguno"), _MINORS),
                _column("contacto_urgencia", values.phone, _CONTACT, "bigint"),
                _text(
                    "indicaciones_enfermeria",
                    pick("Avisar ante dificultad respiratoria", "Medir glucemia"),
                    "salud del estudiante",
                    _MINORS,
                ),
            ),
            table(
                "asistencia",
                _column("documento_estudiante", values.plain_rut, _MINORS),
                _column("jornada_fecha", values.day(2023, 2025), _MINORS, "date"),
                _column("presente", fake.boolean, _MINORS, "boolean"),
                _column("curso", pick("5A", "6B", "7A", "8B"), _MINORS),
                _text(
                    "justificacion_inasistencia",
                    pick("Control odontológico", "Viaje familiar"),
                    "motivo de inasistencia del estudiante",
                    _MINORS,
                ),
            ),
            table(
                "evaluaciones",
                _column("estudiante_evaluado", fake.name, _MINORS),
                _column("asignatura", pick("matemática", "historia", "ciencias")),
                _column("puntaje", number(0, 100), _MINORS, "integer"),
                _column("profesor_nombre", fake.name, _IDENTIFIER),
                _text(
                    "devolucion_pedagogica",
                    pick("Mejoró su expresión escrita", "Reforzar las fracciones"),
                    "desempeño del estudiante",
                    _MINORS,
                ),
            ),
            table(
                "transporte_escolar",
                _column("pasajero_escolar", fake.name, _MINORS),
                _column("domicilio_pasajero", fake.street_address, _MINORS),
                _column("conductor_nombre", fake.name, _IDENTIFIER),
                _trap(
                    "patente_bus_concesion", code("????##"), "vehículo de la empresa de transporte"
                ),
                _column("itinerario_codigo", code("BUS-###")),
            ),
            table(
                "comedor",
                _column("estudiante_comensal", fake.name, _MINORS),
                _column(
                    "restriccion_alimentaria", pick("sin gluten", "sin nueces", "ninguna"), _MINORS
                ),
                _column("proveedor_nombre", fake.company),
                _trap("fono_central_casino", values.company_phone, "teléfono de la concesionaria"),
                _column("turno_comida", pick("primero", "segundo")),
            ),
            table(
                "retiros_autorizados",
                _column("estudiante_retirado", fake.name, _MINORS),
                _column("adulto_autorizado", fake.name, _IDENTIFIER),
                _column("documento_autorizado", values.rut, _IDENTIFIER),
                _column("celular_autorizado", values.phone, _CONTACT, "bigint"),
                _column("permiso_vigente", fake.boolean, _MINORS, "boolean"),
            ),
            table(
                "actividades",
                _column("participante_nombre", fake.name, _MINORS),
                _column("actividad_nombre", pick("ajedrez", "fútbol", "coro")),
                _column("monitor_nombre", fake.name, _IDENTIFIER),
                _column("monitor_correo", values.email, _CONTACT),
                _column("permiso_firmado", fake.boolean, _MINORS, "boolean"),
            ),
            table(
                "biblioteca",
                _column("lector_escolar", fake.name, _MINORS),
                _column("libro_codigo", code("LIB-####")),
                _column("prestamo_fecha", values.day(2023, 2025), _MINORS, "date"),
                _column("devuelto", fake.boolean, _MINORS, "boolean"),
                _text(
                    "constancia_ejemplar",
                    pick("Cubierta con desgaste", "Ejemplar sin anotaciones"),
                    "estado físico del libro",
                ),
            ),
        ],
    )


def build_dataset(seed: int = DEFAULT_SEED) -> Dataset:
    fake = Faker("es_CL")
    fake.seed_instance(seed)
    values = _Values(fake)
    return Dataset([_veterinary(values), _ecommerce(values), _school(values)])


def label_rows(dataset: Dataset) -> list[dict[str, str]]:
    rows = []
    for schema in dataset.schemas:
        for table in schema.tables:
            for column in table.columns:
                label = column.label
                rows.append(
                    {
                        "schema": schema.name,
                        "table": table.name,
                        "column": column.name,
                        "split": schema.split,
                        "personal": "true" if label.personal else "false",
                        "sensitive": "true" if label.sensitive else "false",
                        "category": label.category.value if label.category is not None else "",
                        "note": label.note,
                    }
                )
    return rows


def write_labels(dataset: Dataset, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=_CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(label_rows(dataset))

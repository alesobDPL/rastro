# F1 · Escaneo Postgres medible · Plan de implementación

[Volver al inicio](../../00-inicio.md)

Estado: **Aprobado** por el propietario el 2026-11-27 (propuesto el mismo día), junto con sus 7 decisiones.

> **Cómo se ejecuta:** lo implementa Codex mediante encargos por lotes (skill `proyecto-ordenado`). Claude redacta cada encargo a partir de este plan, lo lanza, audita la entrega e integra el lote en `feat/escaneo-postgres-medible`. Codex no hace commits: deja los cambios en su worktree y el script de Claude los registra. Los pasos usan casillas (`- [ ]`).

**Objetivo:** `rastro scan` inventaría una base Postgres, detecta datos personales por nombre y por patrón, enmascara los valores y entrega un JSON; `eval/evaluate.py` mide precisión y recall contra un dataset sintético etiquetado.

**Arquitectura:** un conector Postgres de solo lectura entrega el esquema y una muestra de valores en memoria; el escáner pasa cada columna por la detección (capa de nombre, capa de patrón, contexto que anula, clasificación) y por el enmascarador, y arma el contrato Pydantic `Scan`. El dataset y sus etiquetas se construyen aislados de las reglas, y la evaluación compara el JSON con las etiquetas.

**Stack:** Python ≥ 3.11 · Typer · SQLAlchemy 2 + psycopg 3 · Pydantic 2 · PyYAML · pytest · Faker · ruff · Postgres 16 en Docker.

**Spec:** [2026-11-26-escaneo-postgres-medible-design.md](../specs/2026-11-26-escaneo-postgres-medible-design.md) (Aprobado 2026-11-27). Cada tarea indica qué secciones del spec lee su encargo.

## Global Constraints

Todo encargo cumple esta sección además de su tarea. Su texto es neutral a propósito: no describe reglas de detección ni el contenido del dataset.

- **Versiones:** Python ≥ 3.11. Dependencias de ejecución: `typer>=0.12`, `sqlalchemy>=2.0`, `psycopg[binary]>=3.1`, `pydantic>=2.6`, `pyyaml>=6`. Desarrollo: `pytest>=8`, `faker>=25`, `ruff>=0.5`. Cualquier otra dependencia se pide en `dudas`.
- **Idioma:** identificadores en inglés; mensajes al usuario, progreso y errores en español; claves y valores del JSON en inglés.
- **Valores de la BD:** viven solo en memoria. Nunca se escriben a disco, logs, stderr ni mensajes de error. Un error de tabla es un texto fijo en español, nunca `str(exc)`.
- **Contraseña:** nunca aparece en el JSON, en `Source`, en el progreso, en un mensaje de error ni en un traceback.
- **Umbrales:** solo en `src/rastro/detection/thresholds.py`; nadie más escribe esos números.
- **Categorías y sensibilidad** (spec §7.6): `identifier` → `medium`, `contact` → `low`, `location` → `low`, `financial` → `medium`, `sensitive` → `high` (con `subcategory`), `minors` → `high`.
- **A qué categoría va cada dato** *(precisión del plan sobre §7.6)*: RUT, pasaporte, nombre, apellido, patente del vehículo de una persona, fecha de nacimiento, edad y sexo → `identifier`. Correo y teléfono → `contact`. Dirección, comuna, región y coordenadas → `location`. Tarjeta, cuenta bancaria y sueldo → `financial`. Salud (también la de mascotas, según §7.10), biométrico, origen étnico, creencias, orientación sexual e identidad de género, afiliación política o sindical → `sensitive`. Cualquier dato de un niño, niña o adolescente → `minors` (siempre sensible).
- **Subcategorías de `sensitive`:** `health`, `biometric`, `ethnic_origin`, `beliefs`, `sexual_orientation` (incluye identidad de género y vida sexual), `political_affiliation`, `union_affiliation`.
- **Formato de `eval/dataset/labels.csv`:** encabezado `schema,table,column,split,personal,sensitive,category,note`; `split` es `dev` u `holdout`; `personal` y `sensitive` son `true` o `false`; `category` es una categoría del contrato o vacío si `personal=false`; `note` es texto libre o vacío. UTF-8, separador coma, una fila por columna del dataset.
- **Aislamiento (spec §9):** cada encargo lee solo esta sección, su propia tarea y las secciones del spec que su tarea lista. El de detección (T2) nunca abre `eval/`; el del dataset (T3) nunca abre `src/rastro/detection/`.
- **BD de pruebas:** `RASTRO_TEST_DB_URL`. Las pruebas que la usan llevan la marca `integration` y se saltan si no hay Postgres. Las que crean objetos usan esquemas y roles con prefijo `rastro_test_` y los borran al terminar.

## Comandos

Se copian a la tabla Comandos de `AGENTS.md` al aprobar el plan.

| Acción | Comando |
| --- | --- |
| Instalar | `pip install -e ".[dev]"` |
| Desarrollo (BD) | `docker compose up -d db` |
| Pruebas (todas) | `pytest` |
| Pruebas (un archivo) | `pytest tests/ruta/test_x.py` |
| Lint | `ruff check .` |
| Pruebas visuales, Tipos | no aplica |

## Review Focus

Entradas que el spec implica y que ninguna prueba de tarea cubriría sola; cada línea tiene su prueba en la tarea indicada.

1. **Texto de una excepción de la BD con valores dentro** (por ejemplo, un error de tipo que cita la fila): el campo `error` lleva solo un mensaje fijo por SQLSTATE. Prueba en T4.
2. **Contraseña en la URL** de una conexión que falla: no aparece en stdout, stderr ni en el JSON. Pruebas en T4 y T5.
3. **Identificadores raros** (espacios, mayúsculas, comillas, palabras reservadas): se listan y se muestrean sin error. Prueba en T4.
4. **Valores que no calzan con su tipo en el enmascarador** (vacío, `N/A`, unicode, 1.000 caracteres, un RUT enmascarado como correo): devuelve el genérico sin fallar. Prueba en T4.
5. **Columnas vacías, todas nulas o con menos de 5 valores, y tablas sin filas:** sin hallazgo de patrón, `null_ratio` nulo si no hay filas, sin excepción. Pruebas en T2 y T5.

---

### Task 1: Esqueleto del paquete y contrato JSON (lote 0)

**Lecturas del encargo:** spec §7.6, §7.9, §7.12 (último punto), §8.

**Files:**
- Create: `pyproject.toml`, `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`
- Modify: `.gitignore` (agregar `eval/results/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `*.egg-info/`)
- Create: `src/rastro/__init__.py` (`__version__ = "0.1.0"`), `src/rastro/models.py`, `src/rastro/cli.py` (stub), `src/rastro/connectors/__init__.py`, `src/rastro/detection/__init__.py`, `eval/__init__.py`, `eval/dataset/__init__.py`
- Create: `schemas/scan-v1.schema.json` (generado)
- Test: `tests/conftest.py`, `tests/unit/test_models.py`

**Interfaces:**
- Consumes: nada.
- Produces (`rastro.models`):
  - StrEnums: `Category` (`identifier`, `contact`, `location`, `financial`, `sensitive`, `minors`), `Sensitivity` (`low`, `medium`, `high`), `Status` (`personal`, `ambiguous`, `not_personal`), `Detector` (`name`, `pattern`), `SensitiveSubcategory` (las siete de Global Constraints), `ValueKind` (`rut`, `email`, `phone`, `card`, `plate`, `generic`).
  - `Finding(category: Category, subcategory: SensitiveSubcategory | None = None, sensitivity: Sensitivity, confidence: float [0,1], detector: Detector, rule_id: str, evidence: str)`
  - `Suppression(rule_id: str, context: str, detector: Detector)` *(agregado del plan al contrato, ver Decisiones)*
  - `Column(name: str, data_type: str, nullable: bool, null_ratio: float | None, status: Status, sensitive: bool, categories: list[Category], masked_samples: list[str] (máx. 3), findings: list[Finding], suppressed: list[Suppression] = [])`
  - `Table(schema_name: str` con alias JSON `"schema"`, `name: str, estimated_rows: int | None, sampled_rows: int, error: str | None, columns: list[Column])`, con `populate_by_name`.
  - `Source(engine: Literal["postgresql"], host: str | None, port: int | None, database: str, user: str)`
  - `Settings(sample_size: int, schemas: list[str], excluded_tables: list[str], layers: list[Literal["name", "pattern"]])`
  - `Summary(tables: int, columns: int, personal: int, sensitive: int, ambiguous: int, failed_tables: int)`
  - `Scan(schema_version: Literal["1"] = "1", rastro_version: str, started_at: datetime, finished_at: datetime, source: Source, settings: Settings, summary: Summary, tables: list[Table])`; `Scan.to_json() -> str` (por alias, indentado) y `Scan.from_json(text: str) -> Scan`.
  - `export_json_schema(path: Path) -> None`; `python -m rastro.models` escribe `schemas/scan-v1.schema.json`.
  - Todos los modelos con `extra="forbid"`.
- Produces (pruebas): fixture `pg_url` (sesión) en `tests/conftest.py`: lee `RASTRO_TEST_DB_URL`, intenta conectar con 3 s de espera y hace `pytest.skip` si falta o no responde.
- Produces (CLI stub): `rastro.cli:app` (Typer, con `@app.callback()` y un comando `scan` que aún no hace nada útil), para que el entry point exista.

**Configuración que fija esta tarea:**
- `pyproject.toml`: build hatchling con layout `src/`; proyecto `rastro` 0.1.0; extra `dev`; script `rastro = "rastro.cli:app"`; los `.yml` de `src/rastro/detection/rules/` entran en el paquete.
- pytest: `pythonpath = ["src", "."]`, `addopts = "--import-mode=importlib"`, marca `integration` registrada.
- ruff: `line-length = 100`, `target-version = "py311"`, reglas `E`, `F`, `I`, `UP`, `B`.
- `docker-compose.yml`: servicio `db`, imagen `postgres:16`, puerto `54329:5432`, `POSTGRES_USER=rastro`, `POSTGRES_DB=rastro`, `POSTGRES_PASSWORD=${RASTRO_PG_PASSWORD:-rastro_dev}`, healthcheck con `pg_isready`.
- `.env.example`: `RASTRO_DB_URL` y `RASTRO_TEST_DB_URL`, ambas `postgresql://rastro:rastro_dev@localhost:54329/rastro`. Sin python-dotenv.
- CI: `ubuntu-latest`, Python 3.11, servicio `postgres:16` con los mismos valores ficticios en el puerto 54329; pasos `pip install -e ".[dev]"`, `ruff check .`, `pytest` con `RASTRO_TEST_DB_URL` definida.

- [ ] **Paso 1: Escribir las pruebas que fallan** en `tests/unit/test_models.py`:
  - `test_scan_roundtrip`: un `Scan` con una tabla, una columna y un hallazgo; `Scan.from_json(scan.to_json()) == scan`.
  - `test_table_serializes_schema_alias`: `json.loads(scan.to_json())["tables"][0]` tiene la clave `"schema"` y no `"schema_name"`.
  - `test_schema_version_is_1`: el JSON tiene `"schema_version": "1"`; `Scan.from_json` con `"2"` lanza `ValidationError`.
  - `test_extra_field_rejected`: un campo desconocido en `Column` lanza `ValidationError`.
  - `test_masked_samples_max_3` y `test_confidence_range`: 4 muestras o `confidence=1.2` lanzan `ValidationError`.
  - `test_password_not_a_field`: `"password" not in Source.model_fields`.
  - `test_json_schema_file_up_to_date`: el contenido de `schemas/scan-v1.schema.json` es igual a `Scan.model_json_schema(by_alias=True)`.
- [ ] **Paso 2:** `pytest tests/unit/test_models.py -v` → FALLA (no existe `rastro.models`).
- [ ] **Paso 3:** crear la configuración, el paquete, `models.py` y el stub de CLI; generar el schema con `python -m rastro.models`.
- [ ] **Paso 4:** `pytest tests/unit/test_models.py -v` → PASA; `ruff check .` → sin errores; `pip install -e ".[dev]"` y `rastro --help` → muestra el comando `scan`; `docker compose config` → válido.
- [ ] **Paso 5:** dejar los cambios en la carpeta; el script registra el commit.

---

### Task 2: Detección por nombre y por patrón, y clasificación (lote 1, aislada)

**Lecturas del encargo:** spec §7.4, §7.5, §7.6, §7.7, §7.8 (solo para entender qué se hace con la evidencia). **Nunca** §7.10, `eval/` ni `tests/eval/`.

**Files:**
- Create: `src/rastro/detection/thresholds.py`, `normalize.py`, `validators.py`, `name_rules.py`, `value_patterns.py`, `classify.py`, `detect.py`
- Create: `src/rastro/detection/rules/names.yml`, `rules/context.yml`, `rules/categories.yml`
- Test: `tests/unit/detection/test_normalize.py`, `test_validators.py`, `test_name_rules.py`, `test_value_patterns.py`, `test_classify.py`, `test_detect.py`

**Interfaces:**
- Consumes: `Category`, `Sensitivity`, `SensitiveSubcategory`, `Detector`, `Status`, `ValueKind` de `rastro.models`.
- Produces:
  - `thresholds.py`: `CONFIDENCE_THRESHOLD = 0.6`, `PATTERN_MIN_MATCH_RATIO = 0.6`, `MIN_NON_NULL_VALUES = 5`, `FREE_TEXT_MIN_AVG_LENGTH = 20`.
  - `normalize.py`: `normalize_name(name: str) -> list[str]` (tokens).
  - `validators.py`: `is_valid_rut(value: str) -> bool`, `luhn_ok(digits: str) -> bool`, `is_cl_phone(value: str) -> bool`, `is_plate(value: str) -> bool`, `is_email(value: str) -> bool`.
  - `detect.py`:
    - `Detection(category: Category, subcategory: SensitiveSubcategory | None, sensitivity: Sensitivity, confidence: float, detector: Detector, rule_id: str, kind: ValueKind | None, raw_evidence: str)` (dataclass congelada). En la capa de patrón, `kind` es el tipo del patrón y `raw_evidence` es un valor de la muestra **sin enmascarar** (lo enmascara el escáner). En la capa de nombre, `kind` es `None` y `raw_evidence` son los tokens normalizados que activaron la regla, unidos por espacio (metadato, no un valor).
    - `SuppressionRecord(rule_id: str, context: str, detector: Detector)`; `context` es el token o la condición que anuló (por ejemplo `suffix:id`).
    - `ColumnDetection(detections: list[Detection], suppressed: list[SuppressionRecord])`.
    - `detect_column(*, table: str, column: str, samples: Sequence[str | None]) -> ColumnDetection`. `samples` vacío significa "solo por nombre".
  - `classify.py`: `ColumnVerdict(status: Status, sensitive: bool, categories: list[Category])`; `classify_column(detections: Sequence[Detection], *, column: str, is_text: bool, samples: Sequence[str | None]) -> ColumnVerdict`. `categories` sin duplicados, en el orden de la enum `Category`, solo de detecciones ≥ `CONFIDENCE_THRESHOLD`.
  - `rule_id`: los de nombre empiezan con `name.`; los de patrón son `pattern.rut`, `pattern.email`, `pattern.phone`, `pattern.plate`, `pattern.card` (categorías `identifier`, `contact`, `contact`, `identifier`, `financial`).
  - Los YAML siguen §7.4: cada regla con `id`, tokens o combinaciones, `category`, `subcategory` opcional, `confidence` fija y `unless` opcional; `context.yml` con las listas globales; `categories.yml` con la tabla de sensibilidad. Se cargan con `importlib.resources`.

Reglas que fija el plan: un string vacío o solo espacios cuenta como nulo para la capa de patrón; la anulación de contexto actúa sobre `identifier` y `contact` de ambas capas y nunca sobre `sensitive` ni `minors`; la normalización trata los plurales simples del español (`proveedores` coincide con `proveedor`).

- [ ] **Paso 1: Escribir las pruebas que fallan:**
  - `test_normalize`: `normalize_name("fechaNac2") == ["fecha", "nac", "2"]`; `normalize_name("Dirección_Envío") == ["direccion", "envio"]`; `normalize_name("RUTCliente") == ["rut", "cliente"]`.
  - `test_validators`: `is_valid_rut` es verdadero para `"12.345.678-5"`, `"12345678-5"`, `"10.000.013-K"`, `"10000013-k"`, `"10.000.004-0"` y falso para `"12.345.678-4"`, `"12345678"`, `"abc"`; `luhn_ok("4111111111111111")` verdadero y `luhn_ok("4111111111111112")` falso; `is_cl_phone` verdadero para `"+56 9 8765 4321"`, `"987654321"`, `"56987654321"`, `"+56-2-2345-6789"` y falso para `"12345"`; `is_plate` verdadero para `"AB1234"`, `"BBCD12"`, `"BB-CD-12"` y falso para `"BACD12"` (vocal entre las 4 letras); `is_email("juana.perez@gmail.com")` verdadero, `is_email("juana@")` falso.
  - `test_name_rules`: `detect_column(table="personas", column="rut", samples=[])` da un hallazgo `identifier` con `confidence == 0.9` y `detector == "name"`; `column="fono_contacto"` da `contact` con 0.8; `column="rut_dv"` y `column="digito_verificador"` dan `identifier`; `column="diagnostico"` da `sensitive` con `subcategory == "health"`; `column="nombre_alumno"` da `minors`; `column="cantidad"` no da nada.
  - `test_context_suppression`: `detect_column(table="proveedores", column="rut", samples=[])` no tiene detecciones `identifier` y su `suppressed` tiene un registro con `context` que nombra el token de organización; `column="tipo_email"` y `column="email_id"` quedan anulados; `detect_column(table="tickets_soporte", column="diagnostico", samples=[])` conserva su hallazgo `sensitive`; `detect_column(table="empresas", column="contacto", samples=["ana@x.cl"] * 6)` anula también el hallazgo `pattern.email`.
  - `test_value_patterns`: 4 RUT válidos → ninguna detección de patrón; 4 válidos de 6 no nulos → `pattern.rut` con `confidence ≈ 0.667`; 3 de 6 → ninguna; 10 valores `None` o `""` → ninguna; teléfonos solo en dígitos (`"987654321"`, `"56987654321"`) y una tarjeta como número (`"4111111111111111"`) se detectan; `raw_evidence` de una detección de patrón es uno de los valores de la muestra.
  - `test_classify`: una detección ≥ 0.6 → `personal`; sin detecciones, `is_text=True` y `column="observaciones"` → `ambiguous`; sin detecciones, texto y muestra con promedio ≥ 20 caracteres y espacios → `ambiguous`; sin detecciones y `is_text=False` → `not_personal`; una detección `minors` ≥ 0.6 → `sensitive=True`; una detección con 0.55 → no cuenta.
- [ ] **Paso 2:** `pytest tests/unit/detection -v` → FALLA.
- [ ] **Paso 3:** implementar los módulos y los YAML. El diccionario cubre como mínimo la lista de §7.4, en español e inglés, con vocabulario genérico.
- [ ] **Paso 4:** `pytest tests/unit/detection -v` → PASA; `ruff check .` → sin errores.
- [ ] **Paso 5:** dejar los cambios; el script registra el commit.

---

### Task 3: Dataset sintético y etiquetas (lote 1, aislada)

**Lecturas del encargo:** spec §7.6 y §7.10. **Nunca** §7.4, §7.5, §7.7 ni `src/rastro/detection/`.

**Files:**
- Create: `eval/dataset/build.py`, `eval/dataset/load.py`, `eval/dataset/labels.csv` (generado) y los módulos de definición de esquemas que Codex necesite dentro de `eval/dataset/`
- Test: `tests/eval/test_dataset.py`, `tests/integration/test_dataset_load.py`

**Interfaces:**
- Consumes: `Category`, `SensitiveSubcategory` de `rastro.models`.
- Produces (`eval.dataset.build`):
  - `DEFAULT_SEED = 21719`
  - `Label(personal: bool, sensitive: bool, category: Category | None, note: str)`
  - `ColumnSpec(name: str, sql_type: str, label: Label)`; `TableSpec(name: str, columns: list[ColumnSpec], rows: list[tuple])`; `SchemaSpec(name: str, split: Literal["dev", "holdout"], tables: list[TableSpec])`; `Dataset(schemas: list[SchemaSpec])`.
  - `build_dataset(seed: int = DEFAULT_SEED) -> Dataset`: pura, sin red ni BD; la misma semilla da el mismo resultado.
  - `Dataset.iter_values() -> Iterator[str]`: `str()` de cada valor no nulo de todas las filas.
  - `label_rows(dataset: Dataset) -> list[dict[str, str]]` y `write_labels(dataset: Dataset, path: Path) -> None` con el formato de Global Constraints.
- Produces (`eval.dataset.load`): `load_dataset(url: str, seed: int = DEFAULT_SEED) -> None`: borra con `CASCADE` y recrea `veterinaria`, `ecommerce` y `colegio`, crea las tablas, inserta las filas y ejecuta `ANALYZE`. CLI: `python -m eval.dataset.load [--url URL] [--seed N]`; sin `--url` usa `RASTRO_DB_URL`.

Reglas que fija el plan: las etiquetas salen de la definición de cada columna (`ColumnSpec.label`), nunca de una salida de Rastro; la `note` empieza con `trampa_fp`, `trampa_fn` o `texto_libre` en esas columnas; el dataset incluye al menos una columna de cada uno de estos tipos SQL: `date`, `boolean`, `uuid`, un entero que guarda teléfonos o tarjetas, y `jsonb` con datos personales; ninguna tabla tiene menos de 100 ni más de 500 filas.

- [ ] **Paso 1: Escribir las pruebas que fallan** en `tests/eval/test_dataset.py`:
  - `test_deterministic`: `build_dataset(1) == build_dataset(1)` y `build_dataset(1) != build_dataset(2)`.
  - `test_schemas_and_splits`: esquemas `veterinaria` y `ecommerce` con `split == "dev"`, `colegio` con `"holdout"`; dev suma entre 35 y 45 tablas y ≥ 250 columnas; `colegio` tiene entre 8 y 12 tablas.
  - `test_rows_per_table`: cada tabla tiene entre 100 y 500 filas y cada fila tiene tantos valores como columnas.
  - `test_minimums`: en dev, ≥ 30 % de columnas con `personal=true`, ≥ 15 con `sensitive=true`, ≥ 10 notas `trampa_fp`, ≥ 10 `trampa_fn`, ≥ 10 `texto_libre`.
  - `test_label_consistency`: `sensitive=true` implica `personal=true`; `personal=false` implica `category` vacía; toda categoría pertenece a `Category`; las columnas `minors` tienen `sensitive=true`.
  - `test_forbidden_example_names`: ninguna columna se llama `campo_3`, `ref_cliente`, `email_template_id`, `rut_empresa_emisora`, `telefono_soporte_tienda`, `obs` ni `diagnostico_mascota`.
  - `test_labels_file_up_to_date`: `eval/dataset/labels.csv` es igual a lo que produce `write_labels(build_dataset())`.
- [ ] **Paso 2: Escribir la prueba de integración que falla** en `tests/integration/test_dataset_load.py` (marca `integration`, fixture `pg_url`): `test_load_from_scratch` carga dos veces seguidas sin error y comprueba que el número de tablas en los tres esquemas coincide con `build_dataset()`.
- [ ] **Paso 3:** `pytest tests/eval tests/integration/test_dataset_load.py -v` → FALLA.
- [ ] **Paso 4:** implementar el generador con Faker `es_CL` y la semilla, la carga y `labels.csv` (generado con `write_labels`).
- [ ] **Paso 5:** con `docker compose up -d db`, `pytest tests/eval tests/integration/test_dataset_load.py -v` → PASA; `ruff check .` → sin errores.
- [ ] **Paso 6:** dejar los cambios; el script registra el commit.

---

### Task 4: Conector Postgres y enmascarador (lote 1)

**Lecturas del encargo:** spec §7.3 y §7.8.

**Files:**
- Create: `src/rastro/connectors/types.py`, `src/rastro/connectors/postgres.py`, `src/rastro/masking.py`
- Test: `tests/unit/test_masking.py`, `tests/unit/test_postgres_errors.py`, `tests/integration/test_postgres_connector.py`

**Interfaces:**
- Consumes: `Source`, `ValueKind` de `rastro.models`.
- Produces (`rastro.connectors.types`):
  - `ColumnInfo(name: str, data_type: str, nullable: bool, sampled: bool, is_text: bool)`
  - `TableInfo(schema: str, name: str, estimated_rows: int | None, columns: list[ColumnInfo])`
  - `TableSample(rows: int, values: dict[str, list[str | None]])`: una lista por columna muestreada, en el orden de las filas.
  - Excepciones con mensaje fijo en español, sin valores ni contraseña: `ConnectionFailed`, `SchemaNotFound(schema)`, `TableReadError`.
  - `Connector` (Protocol): `source() -> Source`, `list_tables(schemas: Sequence[str] = (), exclude: Sequence[str] = ()) -> list[TableInfo]`, `sample(table: TableInfo, n: int) -> TableSample`, `close() -> None`.
- Produces (`rastro.connectors.postgres`): `PostgresConnector(url: str, *, statement_timeout_ms: int = 30000)`, que cumple `Connector`, y su propiedad `engine` (para la prueba de solo lectura).
- Produces (`rastro.masking`): `mask(value: str, kind: ValueKind) -> str`.

Decisiones que fija el plan:
- **Catálogo:** `list_tables` lee de `pg_catalog` (`pg_namespace`, `pg_class` con `relkind` en `r`, `p` y sin particiones hijas, `pg_attribute`, `pg_type`), no de `information_schema.columns`, porque esta oculta las tablas sobre las que el usuario no tiene permisos y el escaneo debe mostrarlas con `error` *(ver Decisiones)*. `data_type` es `format_type(atttypid, atttypmod)`. `sampled` si `typcategory` es `S` o `N`, o el tipo es `json`/`jsonb`; `is_text` si `typcategory` es `S`. `reltuples < 0` → `estimated_rows = None`. Orden: esquema, tabla, número de columna. Sin `schemas` se listan todos menos `pg_catalog`, `information_schema` y `pg_toast*`. `exclude` son globs sobre `esquema.tabla` con `fnmatchcase`. Un esquema pedido que no existe lanza `SchemaNotFound`.
- **Sesión:** URL normalizada a `postgresql+psycopg`; `connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=<ms>"}`. Un fallo al conectar lanza `ConnectionFailed`, cuyo texto no contiene la URL.
- **Muestra:** `select(columnas).limit(n)` con SQLAlchemy Core (`table()`/`column()` citan los identificadores); solo las columnas con `sampled=True`; cada valor a `str` (los `dict`/`list` de JSON con `json.dumps(ensure_ascii=False)`), recortado a 1.000 caracteres. Una tabla sin columnas muestreables no consulta datos y devuelve `TableSample(rows=0, values={})`.
- **Errores de tabla:** `TableReadError` con un mensaje elegido por SQLSTATE: `42501` → "permiso denegado al leer la tabla"; `57014` → "la consulta superó el tiempo máximo"; otro → "error al leer la tabla (código <SQLSTATE>)". Nunca `str(exc)`.
- **Enmascarador** (función pura, ejemplos exactos de §7.8): RUT conserva el primer dígito y el DV; correo conserva la primera letra de la parte local, la primera letra del dominio y el `.tld` final; teléfono conserva los separadores, los 3 primeros dígitos si empieza con `56` (si no, el primero) y los 2 últimos; tarjeta conserva los 4 últimos dígitos y los separadores; patente conserva el primer y el último carácter; genérico conserva la primera letra de cada tramo de letras, la puntuación y los espacios, y cambia los dígitos por `#`. Si el valor no tiene la forma del tipo pedido, se usa el genérico.

- [ ] **Paso 1: Escribir las pruebas unitarias que fallan:**
  - `tests/unit/test_masking.py`: los seis ejemplos de §7.8 dan exactamente su salida (`mask("12.345.678-5", ValueKind.RUT) == "1*.***.***-5"`, etc.); `mask("987654321", PHONE) == "9******21"`; `mask("12345678-K", RUT) == "1*******-K"`.
  - Review Focus 4: `mask("", GENERIC) == ""`; `mask("N/A", GENERIC) == "N/A"`; `mask("Ñuñoa Peñalolén", GENERIC) == "Ñ**** P********"`; `mask("12.345.678-5", EMAIL) == "##.###.###-#"`; `len(mask("a" * 1000, GENERIC)) == 1000`; `mask("4111 1111 1111 1111", PLATE)` no lanza excepción.
  - `tests/unit/test_postgres_errors.py` (Review Focus 1 y 2): la función que traduce una excepción de psycopg a `TableReadError` devuelve el mensaje fijo para `42501`, `57014` y uno desconocido, aunque el texto original de la excepción contenga `"valor-secreto-123"`; `str(ConnectionFailed(...))` creado al fallar con `postgresql://u:Clave_Secreta_9@127.0.0.1:1/db` no contiene `Clave_Secreta_9`.
- [ ] **Paso 2: Escribir las pruebas de integración que fallan** en `tests/integration/test_postgres_connector.py` (marca `integration`, fixture `pg_url`; crean el esquema `rastro_test_conn` y el rol `rastro_test_reader` y los borran al terminar):
  - `test_lists_tables_and_types`: una tabla con `text`, `integer`, `jsonb`, `date` y `uuid` → `sampled` verdadero en las tres primeras y falso en `date` y `uuid`; `is_text` solo en `text`.
  - `test_sample_limit_and_json`: 10 filas, `sample(t, 5).rows == 5`; un `jsonb` llega como texto JSON; un valor de 1.500 caracteres llega con 1.000.
  - `test_read_only_session`: `with connector.engine.connect() as c: c.execute(text("CREATE TABLE rastro_test_conn.x(i int)"))` lanza un error de transacción de solo lectura.
  - `test_permission_denied_table`: conectado como `rastro_test_reader` (con `USAGE` en el esquema y `SELECT` solo en una de dos tablas), `list_tables` devuelve las dos y `sample` sobre la otra lanza `TableReadError("permiso denegado al leer la tabla")`.
  - `test_odd_identifiers` (Review Focus 3): la tabla `"Tabla Rara"` con columnas `"Nombre Completo"`, `"select"` y `"col""comilla"` se lista y se muestrea, y `values` tiene esas tres claves exactas.
  - `test_unknown_schema`: `list_tables(schemas=["no_existe"])` lanza `SchemaNotFound`.
  - `test_exclude_glob`: `exclude=["rastro_test_conn.tmp_*"]` deja fuera `tmp_a` y conserva el resto.
- [ ] **Paso 3:** `pytest tests/unit/test_masking.py tests/unit/test_postgres_errors.py tests/integration/test_postgres_connector.py -v` → FALLA.
- [ ] **Paso 4:** implementar `types.py`, `postgres.py` y `masking.py`.
- [ ] **Paso 5:** con la BD levantada, el mismo comando → PASA; `ruff check .` → sin errores.
- [ ] **Paso 6:** dejar los cambios; el script registra el commit.

---

### Task 5: Escáner y CLI (lote 2)

**Lecturas del encargo:** spec §7.1, §7.2, §7.7, §7.8, §7.9, §7.12.

**Files:**
- Create: `src/rastro/scanner.py`
- Modify: `src/rastro/cli.py` (reemplaza el stub)
- Test: `tests/unit/test_scanner.py`, `tests/unit/test_cli.py`, `tests/integration/test_scan_e2e.py`

**Interfaces:**
- Consumes: modelos de T1; `Connector`, `TableInfo`, `TableSample`, `TableReadError`, `ConnectionFailed`, `SchemaNotFound`, `PostgresConnector` de T4; `mask` de T4; `detect_column`, `Detection`, `classify_column`, `CONFIDENCE_THRESHOLD` de T2; `build_dataset`, `load_dataset`, `DEFAULT_SEED` de T3 (solo en la prueba de integración).
- Produces:
  - `ScanRequest(sample_size: int = 50, schemas: list[str] = [], exclude_tables: list[str] = [])`
  - `run_scan(connector: Connector, request: ScanRequest, progress: Callable[[str], None] | None = None) -> Scan`

Reglas que fija el plan:
- Por columna: `detect_column` con los valores de la muestra (o `[]` si no se muestrea o la tabla falló); `classify_column`; `findings` = todas las detecciones (también las < 0,6), con `evidence` = `mask(raw_evidence, kind)` en las de patrón y `raw_evidence` tal cual en las de nombre; `suppressed` desde los `SuppressionRecord`.
- `masked_samples`: los 3 primeros valores no nulos, no vacíos y distintos de la muestra, enmascarados con el `kind` de la detección de patrón de mayor confianza o, si no hay, con `generic`.
- `null_ratio` = nulos / filas muestreadas; `None` si la columna no se muestrea o la tabla tiene 0 filas.
- Una tabla con `TableReadError` queda con `error`, `sampled_rows = 0` y sus columnas evaluadas solo por nombre *(ver Decisiones)*; el escaneo sigue.
- `summary` cuenta tablas, columnas, columnas `personal`, `sensitive`, `ambiguous` y tablas con `error`. `settings.layers = ["name", "pattern"]`. Fechas en UTC.
- CLI: `rastro scan [URL] [-o ARCHIVO] [--schema NOMBRE]... [--exclude-table PATRÓN]... [--sample-size 50]`. URL desde el argumento o `RASTRO_DB_URL` (gana el argumento). JSON a stdout o a `-o`; progreso a stderr. Salida 0 si terminó (aunque fallen tablas); 2 si falta la URL o el esquema de la URL no es `postgresql`/`postgres`; 1 si falla la conexión, un esquema no existe o hay un error inesperado (mensaje genérico en español, sin traceback). Typer con `pretty_exceptions_enable=False`.

- [ ] **Paso 1: Escribir las pruebas unitarias que fallan** (`tests/unit/test_scanner.py` con un conector falso en memoria que cumple `Connector`; `tests/unit/test_cli.py` con `typer.testing.CliRunner`):
  - `test_scan_builds_contract`: dos tablas con valores ficticios → `Scan` válido, `summary.tables == 2`, `summary.columns` correcto, `schema_version == "1"`.
  - `test_masked_samples_and_evidence`: una columna con 6 RUT válidos → `status == "personal"`, `masked_samples` con 3 elementos enmascarados como RUT, ningún RUT original en `scan.to_json()`.
  - `test_failed_table_continues` (Review Focus 1): el conector falso lanza `TableReadError` en una tabla → esa tabla tiene `error`, `sampled_rows == 0` y sus columnas evaluadas por nombre; la otra tabla está completa; `summary.failed_tables == 1`.
  - `test_empty_and_null_columns` (Review Focus 5): una tabla de 0 filas → `null_ratio is None` y sin hallazgos de patrón; una columna toda nula → `null_ratio == 1.0`; una columna con 3 valores → sin hallazgo de patrón.
  - `test_suppressed_propagated`: los `SuppressionRecord` del detector llegan a `Column.suppressed`.
  - `test_cli_missing_url_exit_2`: sin argumento ni `RASTRO_DB_URL` → código 2 y mensaje en español.
  - `test_cli_non_postgres_exit_2`: `mysql://u:p@h/db` → código 2.
  - `test_cli_connection_failure_hides_password` (Review Focus 2): `postgresql://u:Clave_Secreta_9@127.0.0.1:1/db` → código 1 y `Clave_Secreta_9` no aparece en stdout ni stderr.
- [ ] **Paso 2: Escribir las pruebas de integración que fallan** en `tests/integration/test_scan_e2e.py` (marca `integration`; carga el dataset con `load_dataset(pg_url, DEFAULT_SEED)`):
  - `test_scan_dataset_e2e`: `rastro scan <pg_url> -o <tmp>/scan.json` → código 0; el archivo se valida con `Scan.from_json`; aparecen los tres esquemas del dataset; tarda menos de 120 s.
  - `test_privacy_no_raw_values`: para cada valor de `build_dataset(DEFAULT_SEED).iter_values()` con 4 o más caracteres, que no es igual a un nombre de esquema, tabla o columna, ni a una clave o valor de enum del contrato, y que cambia al enmascararlo con `generic`: el valor no aparece en el JSON. Los valores de solo dígitos con menos de 6 caracteres se buscan solo dentro de `masked_samples` y `evidence`, no en todo el JSON (pueden coincidir con fechas o conteos).
  - `test_password_not_in_output`: la contraseña de `pg_url` no aparece en el JSON.
- [ ] **Paso 3:** `pytest tests/unit/test_scanner.py tests/unit/test_cli.py tests/integration/test_scan_e2e.py -v` → FALLA.
- [ ] **Paso 4:** implementar `scanner.py` y `cli.py`.
- [ ] **Paso 5:** con la BD levantada, el mismo comando → PASA; `pytest` completo → PASA; `ruff check .` → sin errores.
- [ ] **Paso 6:** dejar los cambios; el script registra el commit.

---

### Task 6: Evaluación (lote 2)

**Lecturas del encargo:** spec §7.9 y §7.11.

**Files:**
- Create: `eval/evaluate.py`
- Test: `tests/eval/test_evaluate.py`

**Interfaces:**
- Consumes: `Scan`, `Status`, `Detector` de `rastro.models`; formato de `labels.csv` de Global Constraints. No importa nada de `eval/dataset/`.
- Produces:
  - `LabelRow(schema: str, table: str, column: str, split: str, personal: bool, sensitive: bool, category: str, note: str)`; `load_labels(path: Path) -> list[LabelRow]`.
  - `SplitMetrics(split, labeled, tp, fp, fn, tn, precision: float | None, recall: float | None, f1: float | None, sensitive_recall: float | None, ambiguous: int, ambiguous_personal: int, by_layer: dict[str, int], suppressions: dict[str, int], false_positives: list[str] | None, false_negatives: list[str] | None)`; `by_layer` con las claves `name_only`, `pattern_only`, `both`.
  - `Metrics(splits: dict[str, SplitMetrics], unlabeled: list[str])`.
  - `evaluate(scan: Scan, labels: Sequence[LabelRow]) -> Metrics`.
  - `main(argv: Sequence[str] | None = None) -> int`: `python eval/evaluate.py <scan.json> <labels.csv>` imprime el resumen en español y guarda `eval/results/metrics-<AAAAMMDD-HHMMSS>.json`.

Reglas que fija el plan: predicho personal = `status == "personal"` (`ambiguous` cuenta como no detectada); predicho sensible = `sensitive`; una columna etiquetada que no aparece en el escaneo cuenta como no detectada; una columna escaneada sin etiqueta se ignora y se lista en `unlabeled` con un aviso; `by_layer` mira, en los verdaderos positivos, qué detectores tienen un hallazgo ≥ 0,6; `suppressions` cuenta por `rule_id` y `context` (clave `"<rule_id>|<context>"`); una división por cero da `None` y se imprime `n/a`. En `holdout`, `false_positives`, `false_negatives` y `suppressions` por clave no se calculan (`None` o solo el total en la clave `"total"`), y ningún nombre de columna de `holdout` se imprime ni se guarda.

- [ ] **Paso 1: Escribir las pruebas que fallan** en `tests/eval/test_evaluate.py`, con un `Scan` construido con los modelos y etiquetas en memoria:
  - `test_confusion_and_scores`: cuatro columnas `dev` (personal detectada, personal `ambiguous`, no personal detectada, no personal no detectada) → `tp=1, fn=1, fp=1, tn=1`, `precision == recall == f1 == 0.5`.
  - `test_missing_labeled_column_is_fn` y `test_unlabeled_column_ignored`.
  - `test_sensitive_recall_and_ambiguous`: valores esperados de `sensitive_recall`, `ambiguous` y `ambiguous_personal`.
  - `test_by_layer`: un verdadero positivo con hallazgo solo de nombre, otro solo de patrón y otro con ambos → `{"name_only": 1, "pattern_only": 1, "both": 1}`.
  - `test_suppressions_counted`: dos columnas con el mismo `Suppression` → cuenta 2.
  - `test_holdout_hides_errors`: un falso positivo en `holdout` → `false_positives is None`, y la salida de `main` (capturada con `capsys`) y el JSON guardado (en `tmp_path`) no contienen el nombre de esa columna.
  - `test_division_by_zero`: sin positivos → `precision is None`.
- [ ] **Paso 2:** `pytest tests/eval/test_evaluate.py -v` → FALLA.
- [ ] **Paso 3:** implementar `eval/evaluate.py` (la carpeta de resultados es configurable en `main` para la prueba).
- [ ] **Paso 4:** `pytest tests/eval/test_evaluate.py -v` → PASA; `ruff check .` → sin errores.
- [ ] **Paso 5:** dejar los cambios; el script registra el commit.

---

### M1: Línea base (Claude, sin código)

- [ ] Integrar el lote 2 y correr `pytest` completo en la rama.
- [ ] `docker compose up -d db`; `python -m eval.dataset.load`; `rastro scan -o eval/results/scan-base.json`; `python eval/evaluate.py eval/results/scan-base.json eval/dataset/labels.csv`.
- [ ] Registrar en `docs/privado/` las cifras de dev y holdout y el tiempo del escaneo. Presentarlas al propietario.
- [ ] Redactar el encargo de T7 con la lista de falsos positivos y negativos de **dev** (sin valores) como única entrada.

### Task 7: Ronda de ajuste (lote 3)

**Lecturas del encargo:** spec §7.4, §7.5, §7.7; la lista de errores de dev que trae el encargo. **Nunca** `eval/dataset/` ni nada del esquema `colegio`.

**Files:**
- Modify: `src/rastro/detection/rules/*.yml`, `src/rastro/detection/thresholds.py` y, si hace falta, `name_rules.py` o `value_patterns.py`
- Test: `tests/unit/detection/*`

**Interfaces:** no cambia ninguna firma de T2.

Reglas: cada cambio corrige una clase de error, no una columna: los tokens nuevos son vocabulario genérico y ningún token es el nombre completo de una columna del dataset. Cada regla nueva o modificada lleva una prueba con un nombre de columna inventado distinto de los de la lista. Un cambio de umbral se justifica en `desviaciones` con la cifra que lo motiva.

- [ ] **Paso 1:** por cada clase de error, escribir la prueba que falla con un ejemplo inventado.
- [ ] **Paso 2:** `pytest tests/unit/detection -v` → FALLA en las pruebas nuevas.
- [ ] **Paso 3:** ajustar reglas o umbrales.
- [ ] **Paso 4:** `pytest` completo → PASA; `ruff check .` → sin errores.
- [ ] **Paso 5:** dejar los cambios; el script registra el commit.

### M2: Medición final y README (Claude)

- [ ] Volver a escanear y evaluar; registrar en `docs/privado/` las cifras antes y después, de dev y holdout.
- [ ] Escribir `README.md`: qué hace Rastro, instalación, `docker compose up -d db`, carga del dataset, `rastro scan`, evaluación, y la tabla de métricas antes y después (dev y holdout).
- [ ] Presentar al propietario la revisión final de la rama.

---

## Decisiones del plan

Todas **Aprobadas** por el propietario el 2026-11-27 junto con el plan.

1. **`Column.suppressed` en el contrato v1.** El spec pide contar las anulaciones en la evaluación; para que `evaluate.py` lo haga solo desde el JSON, cada columna lleva la lista de anulaciones (regla y contexto, sin valores).
2. **Evidencia de la capa de nombre sin enmascarar.** Son los tokens del nombre de la columna (metadato), no un valor de la BD. La evidencia de la capa de patrón sí va enmascarada.
3. **Catálogo desde `pg_catalog` en lugar de `information_schema.columns`.** `information_schema` oculta las tablas sin permisos, y entonces nunca aparecerían con `error` como pide el spec.
4. **Tabla con error evaluada por nombre.** Sus columnas aparecen con los hallazgos de la capa 1 en vez de quedar vacías.
5. **Mapeo de categorías** de Global Constraints (fecha de nacimiento, edad y sexo como `identifier`; identidad de género en `sexual_orientation`; salud de mascotas como `sensitive`).
6. **Esquema inexistente en `--schema` → código 1**, como un error de conexión.
7. **README lo escribe Claude** en M2 (no es código), en vez de un encargo.

## Lotes

| Lote | Tareas | Archivos que tocan | Depende de |
| --- | --- | --- | --- |
| 0 | T1 · esqueleto y contrato | `pyproject.toml`, `.gitignore`, `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`, `src/rastro/{__init__,models,cli}.py`, `src/rastro/{connectors,detection}/__init__.py`, `eval/__init__.py`, `eval/dataset/__init__.py`, `schemas/scan-v1.schema.json`, `tests/conftest.py`, `tests/unit/test_models.py` | — |
| 1 | T2 · detección (aislada) | `src/rastro/detection/**` (salvo `__init__.py`), `tests/unit/detection/**` | Lote 0 |
| 1 | T3 · dataset (aislada) | `eval/dataset/**` (salvo `__init__.py`), `tests/eval/test_dataset.py`, `tests/integration/test_dataset_load.py` | Lote 0 |
| 1 | T4 · conector y enmascarador | `src/rastro/connectors/{types,postgres}.py`, `src/rastro/masking.py`, `tests/unit/test_masking.py`, `tests/unit/test_postgres_errors.py`, `tests/integration/test_postgres_connector.py` | Lote 0 |
| 2 | T5 · escáner y CLI | `src/rastro/scanner.py`, `src/rastro/cli.py`, `tests/unit/test_scanner.py`, `tests/unit/test_cli.py`, `tests/integration/test_scan_e2e.py` | Lote 1 (T2, T3, T4) |
| 2 | T6 · evaluación | `eval/evaluate.py`, `tests/eval/test_evaluate.py` | Lote 0 |
| M1 | Línea base (Claude) | `docs/privado/` | Lote 2 |
| 3 | T7 · ajuste con errores de dev | `src/rastro/detection/rules/*.yml`, `thresholds.py`, `tests/unit/detection/**` | M1 |
| M2 | Medición final y README (Claude) | `README.md`, `docs/privado/` | Lote 3 |

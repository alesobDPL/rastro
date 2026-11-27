# F1 · Escaneo Postgres medible

[Volver a specs](README.md) · [Hoja de ruta](../../hoja-de-ruta.md)

Estado: **Aprobado** por el propietario el 2026-11-27 (propuesto el 2026-11-26), incluidas las decisiones de Claude marcadas en el texto y en §10.

## 1. Intención

Rastro es un CLI local que inventaría los datos personales de una base de datos para ayudar a cumplir la Ley 21.719 (vigencia prevista entre 2026 y 2027). El objetivo principal del proyecto es el portafolio y las entrevistas. Por eso la prueba de valor es una **cifra medida**: precisión y recall contra un dataset etiquetado. Esta primera funcionalidad entrega el escaneo de Postgres con las dos capas deterministas (nombre de columna y patrón de valores) y la medición de punta a punta, para que cada funcionalidad posterior muestre cuánto mejora esa cifra.

La promesa de privacidad rige desde ya: **ningún valor real leído de la base sale del proceso**, ni en el JSON, ni en los logs, ni en los mensajes de error.

## 2. Objetivos

1. `rastro scan` se conecta a Postgres, lee el esquema, toma una muestra por tabla y clasifica cada columna.
2. Capa 1 (nombre) y capa 2 (patrón de valores) con reglas genéricas para Chile.
3. Enmascarador: todo valor que aparece en la salida está enmascarado.
4. Salida JSON con un contrato versionado (Pydantic), base de las funcionalidades F2 a F6.
5. Dataset sintético chileno etiquetado (veterinaria + e-commerce), reproducible con una semilla, cargado en un Postgres de Docker.
6. Script de evaluación: compara el JSON con las etiquetas y entrega precisión, recall y la lista de errores.

## 3. No objetivos (llegan en otras funcionalidades)

- Capa IA y llamadas a OpenAI (F2). F1 solo marca las columnas `ambiguous`.
- Reportes HTML, Markdown o CSV; puntaje de riesgo; recomendaciones; `rastro.yml` (F3).
- MySQL (F4), escaneo de código (F5), Privacy CI (F6), publicación en PyPI e imagen Docker de Rastro (F7).

## 4. Antiobjetivos (fracaso aunque funcione)

- Un valor real de la base aparece en el JSON, en la consola, en un log, en un traceback o en un snapshot de prueba.
- Rastro escribe o bloquea algo en la base escaneada.
- La URL de conexión se muestra con la contraseña.
- Las reglas de detección mencionan nombres de columnas propios del dataset. Las reglas deben ser genéricas; si se ajustan para "aprobar" el dataset, la métrica pierde valor.

## 5. Restricciones

- Python ≥ 3.11 (el propietario tiene 3.11.0). Entorno con `venv` + `pip` y `pyproject.toml`; no hay `uv` instalado.
- Paquete importable `rastro`; comando `rastro`. El nombre de distribución en PyPI se decide en F7.
- Dependencias de ejecución: Typer, SQLAlchemy 2, psycopg 3, Pydantic 2, PyYAML. De desarrollo: pytest, Faker, ruff.
- Postgres 16 en `docker-compose.yml`, puerto local 54329 para no chocar con otro Postgres.
- Identificadores de código y claves del JSON en inglés; mensajes al usuario en español (regla de [AGENTS.md](../../../AGENTS.md)).
- Repo público: el dataset es 100 % sintético. No se versiona ningún `.env`; solo `.env.example` con valores ficticios.

## 6. Enfoques considerados

| Enfoque | Qué se gana | Qué cuesta |
| --- | --- | --- |
| **A. Medir primero** (elegido por el propietario el 2026-11-26) | Cifra real desde la semana 1; cada mejora se nota en la métrica | F1 es la funcionalidad más grande y no hay nada visual hasta F3 |
| B. Plan semanal original | Sigue el calendario del brief | Las capas 1–2 se ajustan a ciegas una semana |
| C. Demo primero | Algo vistoso antes | Fija el reporte antes de conocer los hallazgos; métricas al final |

## 7. Diseño

### 7.1 Flujo

```
rastro scan  ──▶ conector Postgres ──▶ esquema + muestra (en memoria)
                                          │
                                          ▼
                     capa 1 (nombre) + capa 2 (patrón) ──▶ hallazgos
                                          │
                                          ▼
                     clasificación de la columna ──▶ enmascarador ──▶ JSON
                                                                       │
eval/evaluate.py  ◀── etiquetas del dataset ◀──────────────────────────┘
```

La evaluación lee el JSON; no vuelve a conectarse a la base. Así sirve igual para F2 y F4.

### 7.2 CLI

```
rastro scan [URL] [-o salida.json] [--schema NOMBRE]... [--exclude-table PATRÓN]...
            [--sample-size 50]
```

- La URL también se puede pasar por la variable `RASTRO_DB_URL`, para que la contraseña no quede en el historial de la terminal. Si llegan las dos, gana el argumento.
- `--schema` se puede repetir; por defecto se escanean todos los esquemas que no son del sistema (`pg_catalog`, `information_schema`, `pg_toast*`).
- `--exclude-table` acepta patrones tipo glob sobre `esquema.tabla`.
- Sin `-o`, el JSON va a la salida estándar; el progreso y los avisos van a la salida de errores.
- Códigos de salida: `0` escaneo completo (aunque alguna tabla haya fallado, eso queda en el JSON); `1` no se pudo conectar o leer el esquema; `2` uso inválido.

### 7.3 Conector Postgres

- Sesión de solo lectura (`default_transaction_read_only = on`) y `statement_timeout` de 30 s por consulta.
- Esquema desde `information_schema.columns`: esquema, tabla, columna, tipo de dato, si admite nulos. Estimación de filas desde `pg_class.reltuples`.
- Muestra: `SELECT <columnas> FROM <tabla> LIMIT <n>`, con identificadores citados por SQLAlchemy (nunca concatenación de texto). Son las primeras N filas; el muestreo aleatorio queda fuera del MVP.
- Tipos que se muestrean (convertidos a texto): texto (`text`, `varchar`, `char`, `citext`), enteros y numéricos (una tarjeta o un teléfono pueden guardarse como número) y `json`/`jsonb`. Los demás (fechas, booleanos, `bytea`, `uuid`, arreglos, geométricos y otros) no se muestrean: solo se evalúan por nombre. *(Decisión de Claude.)*
- RUT partido en dos columnas (cuerpo entero + `dv`): la capa 2 no lo valida, porque no hay un patrón de "RUT sin DV" (siete u ocho dígitos sueltos generan demasiado ruido). Lo detecta la capa 1 por nombre. *(Decisión de Claude.)*
- Cada valor se convierte a texto y se recorta a 1.000 caracteres en memoria.
- Si una tabla falla (permiso denegado, timeout), se registra en su campo `error` con un mensaje sin valores y el escaneo sigue.
- Los valores solo viven en memoria durante el escaneo. No se escriben a disco ni a logs.

### 7.4 Capa 1: nombre de columna

- Normalización del nombre: minúsculas, sin tildes, separando `snake_case`, `camelCase` y dígitos (`fechaNac2` → `fecha nac 2`).
- Diccionario de tokens en español e inglés por categoría, en un archivo YAML dentro del paquete (`src/rastro/detection/rules/`). Cada regla tiene `id`, tokens o combinaciones, categoría, subcategoría opcional y confianza fija (por ejemplo, `rut` exacto 0,9; `fono` 0,8).
- Debe cubrir como mínimo: RUT o identificación nacional, nombres y apellidos, correo, teléfono, dirección, comuna, región, coordenadas, fecha de nacimiento, edad, sexo o género, tarjeta, cuenta bancaria, sueldo, salud (diagnóstico, enfermedad, alergia, medicamento, licencia médica), datos biométricos, origen étnico, religión o creencias, orientación sexual, afiliación política o sindical, y menores (alumno, hijo, apoderado, fecha de nacimiento de un menor).
- **Contexto que anula** *(decisión de Claude)*. Los hallazgos de las categorías `identifier` y `contact` se anulan (no se emiten), tanto los de la capa 1 como los de la capa 2, cuando:
  - el nombre de la columna o de la tabla contiene un token de organización (por ejemplo `empresa`, `proveedor`, `tienda`, `sucursal`, `soporte`, `institucion`, `company`, `vendor`, `support`, `store`); o
  - el nombre de la columna contiene un token de plantilla o de metadato junto a un token personal (`template`, `plantilla`, `tipo`, `formato`, `estado`, `cantidad`, `count`, `flag`); o
  - el nombre termina en `id` o `codigo` (una clave foránea o un código, no el dato en sí).

  Las listas exactas quedan a quien construye. El formato YAML permite reglas `unless` por regla y listas globales de contexto, y cada anulación queda registrada para la evaluación (cuántas veces actuó). Las categorías `sensitive` y `minors` nunca se anulan, porque es preferible un falso positivo en un dato sensible.
- Las reglas son genéricas. Prohibido escribir reglas a partir de los nombres del dataset (ver §4 y §9).

### 7.5 Capa 2: patrón de valores

Se evalúa sobre los valores no nulos de la muestra. Una regla genera un hallazgo si coincide en al menos el 60 % de esos valores; la confianza es la fracción de coincidencias, con un mínimo de 5 valores no nulos para opinar.

| Patrón | Regla |
| --- | --- |
| RUT | Con o sin puntos, con guion, DV `0-9` o `K`; **dígito verificador válido por módulo 11** |
| Correo | Formato `local@dominio.tld` |
| Teléfono chileno | Móvil `+56 9 XXXX XXXX` y variantes sin `+56`, sin espacios o con guiones; fijo `+56 2…` o de regiones |
| Patente | Formato antiguo `AA1234` y nuevo `BBBB12` (4 consonantes + 2 dígitos), con o sin separadores |
| Tarjeta | 13 a 19 dígitos que pasan **Luhn** |

Un RUT de empresa también pasa el módulo 11. La capa 2 no distingue personas de empresas; esa diferencia la aporta el nombre de la columna o la IA en F2.

### 7.6 Categorías y sensibilidad

| `category` | Ejemplos | `sensitivity` |
| --- | --- | --- |
| `identifier` | RUT, nombre, pasaporte, patente de un vehículo de una persona | `medium` |
| `contact` | correo, teléfono | `low` |
| `location` | dirección, comuna, coordenadas | `low` |
| `financial` | tarjeta, cuenta, sueldo | `medium` |
| `sensitive` | salud, biométrico, origen, orientación sexual, creencias, afiliación (con `subcategory`) | `high` |
| `minors` | datos de niños, niñas y adolescentes | `high` |

La tabla vive en el YAML de reglas para que F3 la ajuste al calcular el riesgo.

### 7.7 Clasificación de la columna

- `personal`: algún hallazgo con confianza ≥ 0,6.
- `ambiguous`: sin hallazgo ≥ 0,6, columna de texto y además el nombre tiene un token de texto libre (`obs`, `nota`, `comentario`, `detalle`, `descripcion`, `mensaje`, `glosa`, `notes`, `comment`) o el largo promedio de la muestra es ≥ 20 caracteres con espacios. En F1 significa "revisar manualmente"; en F2 se envía a la IA.
- `not_personal`: el resto.
- `sensitive: true` si algún hallazgo ≥ 0,6 es de categoría `sensitive` o `minors`.
- Los umbrales (0,6, 5 valores, 20 caracteres) son constantes en un solo lugar del código, porque la evaluación puede justificar ajustarlos.

### 7.8 Enmascarador

Función pura: recibe un valor y el tipo detectado, y devuelve la versión enmascarada.

| Tipo | Ejemplo |
| --- | --- |
| RUT | `12.345.678-5` → `1*.***.***-5` |
| Correo | `juana.perez@gmail.com` → `j**********@g****.com` |
| Teléfono | `+56 9 8765 4321` → `+56 9 **** **21` |
| Tarjeta | `4111 1111 1111 1111` → `**** **** **** 1111` |
| Patente | `BBCD12` → `B****2` |
| Genérico (cualquier otro) | Conserva la primera letra de cada palabra, la puntuación y los espacios: `paciente con diabetes` → `p******* c** d*******`; los dígitos pasan a `#` |

- El JSON lleva como máximo 3 muestras enmascaradas por columna, y la evidencia de cada hallazgo también va enmascarada.
- **Prueba de privacidad obligatoria:** una prueba de integración escanea el dataset y comprueba que ningún valor de la muestra con 4 o más caracteres aparece literalmente en el JSON resultante.
- El enmascarado para enviar texto libre a la IA (que necesita conservar palabras) es otro problema y se diseña en F2.

### 7.9 Contrato JSON (versión `1`)

Modelos Pydantic; el JSON se genera desde ellos y el repo incluye su JSON Schema exportado.

```
Scan
  schema_version: "1"
  rastro_version, started_at, finished_at (ISO 8601, UTC)
  source: engine, host, port, database, user        # nunca la contraseña
  settings: sample_size, schemas, excluded_tables, layers: ["name", "pattern"]
  summary: tables, columns, personal, sensitive, ambiguous, failed_tables
  tables: [Table]

Table
  schema, name, estimated_rows, sampled_rows, error (null o mensaje sin valores)
  columns: [Column]

Column
  name, data_type, nullable, null_ratio (en la muestra)
  status: personal | ambiguous | not_personal
  sensitive: bool
  categories: [category]                            # únicas, de los hallazgos ≥ 0,6
  masked_samples: [str] (≤ 3)
  findings: [Finding]

Finding
  category, subcategory (opcional), sensitivity, confidence (0–1)
  detector: name | pattern                          # F2 agrega "llm"
  rule_id, evidence (enmascarada)
```

Las recomendaciones (`Recommendation`) se agregan en F3 con `schema_version` nuevo.

### 7.10 Dataset sintético

- Dos esquemas de **desarrollo**, `veterinaria` y `ecommerce`, con unas 40 tablas en total, al menos 250 columnas y entre 100 y 500 filas por tabla.
- Un tercer esquema **reservado**, `colegio` (unas 10 tablas, con datos de menores, apoderados y salud escolar), que sirve para medir sin sesgo: nadie ajusta reglas mirando sus errores (ver §7.11 y §9). *(Decisión de Claude.)*
- Generador en Python con Faker `es_CL` (`rut()`, nombres, direcciones, comunas) y semilla fija: la misma semilla produce los mismos datos.
- Debe incluir, como mínimo:
  - al menos el 30 % de columnas personales y al menos 15 sensibles (salud de mascotas y de dueños, datos de menores en e-commerce, etc.);
  - RUT en varios formatos, con y sin puntos, y algunos RUT con DV inválido en columnas que no son de RUT;
  - **trampas de falso positivo** (al menos 10): nombres que parecen personales y no lo son, como `email_template_id`, `rut_empresa_emisora`, `telefono_soporte_tienda`;
  - **trampas de falso negativo** (al menos 10): columnas personales con nombres opacos, como `campo_3` con RUT o `ref_cliente` con correos;
  - al menos 10 columnas de texto libre, algunas con contenido personal o sensible (`obs` con "paciente con diabetes") y otras sin él.
- Los nombres de columna de ejemplo de este documento (`campo_3`, `email_template_id`, etc.) solo ilustran el tipo de trampa: el dataset usa nombres propios, distintos de esos.
- Etiquetas en `eval/dataset/labels.csv`, una fila por columna: `schema, table, column, split (dev | holdout), personal (bool), sensitive (bool), category, note`. Las etiquetas se escriben junto con la definición de cada columna, no después de mirar la salida de Rastro. La lista de categorías es la del contrato (§7.6), que llega en el lote 0.
- Un comando carga el dataset en el Postgres de Docker partiendo desde cero.
- Criterios de etiquetado:
  - un RUT de empresa o un teléfono corporativo no es dato personal (la ley protege a personas naturales);
  - la patente del vehículo de una persona es personal (`identifier`); la de un vehículo de la empresa no lo es;
  - un RUT partido se etiqueta como personal (`identifier`) en sus dos columnas, cuerpo y `dv`;
  - una clave foránea (`cliente_id`) no es dato personal por sí sola.

### 7.11 Evaluación

`python eval/evaluate.py <scan.json> eval/dataset/labels.csv` entrega:

- precisión, recall y F1 sobre "es dato personal", contando `ambiguous` como no detectada;
- recall sobre "es sensible";
- cantidad de columnas `ambiguous` y cuántas de ellas son personales según las etiquetas (lo que F2 puede recuperar);
- aporte de cada capa (columnas detectadas solo por nombre, solo por patrón, por ambas);
- la lista de falsos positivos y falsos negativos (`esquema.tabla.columna`, sin valores);
- cuántas veces actuó cada anulación de contexto (§7.4).

Las métricas se informan por separado para `dev` y `holdout`. La lista de errores se muestra **solo para `dev`**; de `holdout` solo salen las cifras agregadas, para que nadie ajuste reglas mirando sus errores.

Imprime un resumen legible y guarda un JSON con las métricas en `eval/results/` (ignorado por git, salvo que el propietario decida publicar uno). F1 no fija una meta numérica: el objetivo es medir y dejar la línea base.

### 7.12 Pruebas

- Unitarias: validadores (RUT módulo 11 con casos válidos, inválidos y DV `K`; Luhn; teléfonos; patentes), normalización de nombres, reglas de nombre, enmascarador, clasificación y umbrales.
- Integración (marca `integration`, se salta si no hay Postgres): escaneo del dataset de punta a punta, prueba de privacidad (§7.8), sesión de solo lectura (un intento de escritura dentro de la sesión falla) y tabla sin permisos que queda con `error` sin detener el escaneo.
- El escaneo del dataset completo termina en menos de 2 minutos en la máquina del propietario.
- Un workflow de GitHub Actions corre ruff y las pruebas, con un servicio Postgres para las de integración.

## 8. Estructura propuesta

```
src/rastro/
  cli.py                      # Typer
  models.py                   # contrato JSON (Pydantic)
  scanner.py                  # orquesta conector → capas → clasificación → salida
  masking.py
  connectors/postgres.py
  detection/
    normalize.py, name_rules.py, value_patterns.py, validators.py, classify.py
    rules/*.yml
eval/
  dataset/                    # generador, labels.csv
  evaluate.py
tests/
docker-compose.yml
.env.example                  # RASTRO_DB_URL ficticia
```

## 9. Condición para el plan

**Para que la métrica sea creíble,** el dataset con sus etiquetas y las reglas de detección (capas 1 y 2) se implementan en encargos distintos, del mismo lote y en worktrees separados: quien escribe las reglas no ve el dataset y quien escribe el dataset no ve las reglas. El contrato JSON (`models.py`, con la lista de categorías) y el esqueleto del paquete van en un lote 0 previo.

Aislamiento en los encargos *(decisión de Claude)*:

- El encargo de reglas lee §7.4 a §7.8 y nunca §7.10 ni `eval/`.
- El encargo del dataset lee §7.6 y §7.10 y nunca §7.4, §7.5, §7.7 ni `src/rastro/detection/`.
- Ninguno recibe el spec completo.

**Una ronda de ajuste, y solo con `dev`.** Tras la primera evaluación, la línea base queda registrada (dev y holdout). Después, un lote de ajuste puede cambiar reglas y umbrales mirando solo los errores de `dev`, y se vuelve a medir. El README informará las dos cifras, antes y después, y el `holdout` muestra si el ajuste generaliza. El esquema `colegio` no se usa para ajustar en ninguna funcionalidad posterior.

## 10. Decisiones tomadas

| Decisión | Quién | Estado |
| --- | --- | --- |
| Enfoque "medir primero" | Propietario | **Aprobado** el 2026-11-26 |
| Capa IA con OpenAI, opcional con `--llm`, modelo `gpt-6-luna` con esfuerzo `none` y `low` (y `gpt-5-nano` solo si M3 se hace antes de su apagado, 2026-12-11) (F2; corregido el 2026-11-27 por el spec de F2) | Propietario | **Aprobado** el 2026-11-26 |
| Privacy CI solo sobre migraciones `.sql`; falsos positivos en `rastro.yml` (F3, F6) | Claude | **Aprobado** el 2026-11-27 |
| Python ≥ 3.11, venv + pip, Postgres 16 en el puerto 54329 | Claude | **Aprobado** el 2026-11-27 |
| Umbrales (0,6 de confianza, mínimo 5 valores, 20 caracteres para texto libre) | Claude | **Aprobado** el 2026-11-27: ajustables en la ronda de ajuste (§9) |
| Primeras N filas en lugar de muestreo aleatorio | Claude | **Aprobado** el 2026-11-27 |
| Claves y valores del JSON en inglés | Claude | **Aprobado** el 2026-11-27 |
| Tabla de sensibilidad por categoría (§7.6) | Claude | **Aprobado** el 2026-11-27: F3 la revisa |
| Contexto que anula hallazgos de identificador y contacto, nunca los sensibles (§7.4) | Claude | **Aprobado** el 2026-11-27 |
| Patente de una persona = `identifier`; RUT partido detectado solo por nombre (§7.3, §7.6) | Claude | **Aprobado** el 2026-11-27 |
| Tipos muestreados: texto, numéricos y JSON (§7.3) | Claude | **Aprobado** el 2026-11-27 |
| Esquema reservado `colegio` y una ronda de ajuste solo con `dev` (§7.10, §9) | Claude | **Aprobado** el 2026-11-27 |
| Aislamiento por secciones del spec entre los encargos de reglas y de dataset (§9) | Claude | **Aprobado** el 2026-11-27 |

## 11. Lo que queda a quien construye

- Las expresiones regulares exactas y el contenido completo del diccionario de nombres, dentro de lo que exige §7.4 y §7.5.
- La estructura interna de los módulos, siempre que respete el contrato JSON.
- Qué tablas y columnas tiene el dataset, dentro de lo que exige §7.10.
- El formato del progreso en consola y de los mensajes de error, en español y sin valores.

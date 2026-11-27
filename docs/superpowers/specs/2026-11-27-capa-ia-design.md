# F2 · Capa IA para columnas no resueltas

[Volver a specs](README.md) · [Hoja de ruta](../../hoja-de-ruta.md) · [Spec de F1](2026-11-26-escaneo-postgres-medible-design.md) · [Preguntas de diseño](../../privado/fases-y-pruebas/f2-preguntas-de-diseno.md)

Estado: **Propuesto** el 2026-11-27 (subagente Opus, arquitecto). Las decisiones que el propietario tomó el 2026-11-27 figuran como **Aprobado** en §10. Todo lo demás, incluidas las decisiones de Claude marcadas en el texto, está **Propuesto**. Mientras siga así, este documento no autoriza el plan ni la implementación.

## 1. Intención

F1 dejó una cifra medida: recall de 0.777 en dev y de 0.585 en el holdout `colegio`, con recall de sensibles de 0.407 y 0.321. Los errores que quedan no se resuelven con más reglas: texto libre con datos personales o de salud, nombres opacos y columnas que son sensibles por el contexto de la tabla y no por su nombre. F2 agrega una tercera capa, **opcional y explícita** (`--llm`), que envía a un modelo de OpenAI esas columnas sin resolver con muestras enmascaradas, y mide tres cosas: cuánto sube la cifra, qué fracción de columnas se envió y cuánto costó.

La promesa de F1 cambia de forma controlada. Sin `--llm`, ningún dato sale del proceso. Con `--llm` salen, hacia la API de OpenAI, solo nombres de tablas y columnas, tipos y muestras con **enmascarado semántico**: los identificadores se reemplazan por marcadores y las palabras comunes se conservan. Ningún identificador conocido sale.

## 2. Objetivos

1. Una capa `llm` que clasifica columnas candidatas, agrupadas por tabla, y solo puede **subir** el estado de una columna.
2. Un enmascarado semántico para el contenido que se envía, verificado por una prueba de privacidad sobre el contenido enviado.
3. `--llm-dry-run`: escribe exactamente lo que se enviaría y el costo estimado, sin red y sin clave.
4. Control de gasto: tabla de precios versionada, estimación previa, tope duro por escaneo y costo real en el JSON.
5. Contrato JSON versión `2`, que registra el detector `llm`, la configuración y el uso de la capa.
6. Corrección de plurales (N4) en las reglas, medida aparte como línea base «solo reglas».
7. Un conjunto de evaluación **sellado** nuevo, de otros dominios y con trampas de precisión, medido una sola vez.
8. Una medición final (M3) que compara modelos dentro de un presupuesto de USD 4 en total.

## 3. No objetivos

- Otros proveedores de IA (Anthropic, Ollama, Azure). Solo hay una interfaz mínima, con una implementación real (OpenAI) y una falsa para pruebas (§7.5). *(Aprobado por el propietario el 2026-11-27.)*
- Batch API, procesamiento flex o en segundo plano (abaratan, pero agregan asincronía), caché de respuestas y llamadas concurrentes.
- Que la IA baje o anule un hallazgo de las reglas, o resuelva el contexto persona/empresa de los hallazgos anulados.
- Recomendaciones y reportes (F3), MySQL (F4).

## 4. Antiobjetivos (fracaso aunque funcione)

- Un valor que las reglas o las etiquetas reconocen como identificador, contacto o financiero aparece literalmente en lo que se envía a OpenAI.
- La clave de API aparece en el JSON, en la consola, en un log, en un traceback, en un archivo del repo o en el chat.
- Sin `--llm`, Rastro abre una conexión de red hacia un proveedor o importa su SDK.
- Un escaneo gasta más que su tope (`--llm-max-usd`).
- El prompt o sus ejemplos mencionan nombres de tablas o columnas de los datasets. Igual que las reglas de F1, el prompt debe ser genérico.
- El prompt se ajusta mirando el conjunto sellado o `colegio`.

## 5. Restricciones

- Las de F1 §5 siguen vigentes.
- SDK oficial `openai` como **extra opcional** (`pip install -e ".[llm]"`), importado solo cuando se usa `--llm` sin `--llm-dry-run`. Las pruebas y la CI no lo necesitan.
- API Responses de OpenAI con salida estructurada (JSON Schema generado desde Pydantic) y `store: false`, para no pedir que la respuesta quede guardada. *(Decisión de Claude. Quien construye verifica en la documentación vigente del SDK el nombre exacto de cada parámetro.)*
- Clave solo en la variable de entorno `OPENAI_API_KEY`, que se lee y se pasa de forma explícita al cliente. No hay opción `--api-key`, ni archivo, ni `rastro.yml`. El propietario la define en su terminal o en las variables de usuario de Windows, y **nunca la pega en el chat ni la escribe en un archivo del repo**. `.env.example` lleva un valor ficticio y un comentario.
- La implementación completa y la CI usan solo el proveedor falso. El único gasto real ocurre en los hitos H2 y M3 (§9), que corre Claude con la clave que el propietario dejó en su entorno.

## 6. Enfoques considerados

| Enfoque | Qué se gana | Qué cuesta |
| --- | --- | --- |
| A. Solo `ambiguous`, como dice la hoja de ruta | Mínimo envío y mínimo costo | En `colegio` solo 5 de 17 falsos negativos son ambiguos: el recall sube a 0.707 como máximo, por diseño |
| **B. `ambiguous` + `not_personal` sin señal, por tabla, y la IA solo sube** (elegido por el propietario el 2026-11-27) | Llega a los nombres opacos y a los sensibles por contexto; el riesgo de precisión queda acotado | Envía más columnas (ver §7.10) y puede crear falsos positivos, que se miden con trampas |
| C. Todas las columnas | Techo máximo | Contradice «de la capa más barata a la más cara» y expone más datos |

## 7. Diseño

### 7.1 Flujo

```
rastro scan --llm ──▶ (F1) conector ─▶ capas 1 y 2 ─▶ clasificación por reglas
                                                         │
                                                         ▼
                             selección de candidatas (§7.2), agrupadas por tabla
                                                         │
                                                         ▼
                      enmascarado semántico (§7.3) ─▶ payload por tabla (§7.4)
                                                         │
                       ┌── --llm-dry-run: escribe payloads + estimación y termina la capa
                       ▼
             presupuesto (§7.7) ─▶ LLMClient (OpenAI | falso) ─▶ validación Pydantic
                                                         │
                                                         ▼
                                fusión: solo sube (§7.6) ─▶ enmascarador F1 ─▶ JSON v2
```

La capa corre después de la clasificación por reglas y antes de serializar. Las muestras se toman una sola vez, como en F1, y no se vuelve a leer la base.

### 7.2 Columnas candidatas

Una columna es candidata si cumple una de estas dos condiciones:

- su estado por reglas es `ambiguous`; o
- su estado es `not_personal`, no tiene ningún hallazgo de las capas 1 y 2 (de ninguna confianza), ninguna anulación de contexto actuó sobre ella y no es una clave (nombre que termina en `id` o `uuid` según la normalización de F1, o clave primaria). *(Decisión de Claude: las anuladas quedan fuera porque la IA solo puede subir, y subir una columna anulada por contexto de organización sería deshacer las reglas.)*

Se incluyen todos los tipos de datos. Las columnas de tipos que F1 no muestrea (fechas, booleanos) van sin muestras, solo con su nombre y el contexto. Las columnas con estado `personal` nunca se envían.

Límites: `--llm-max-columns` (por defecto 300) por escaneo. Si una tabla tiene más de 25 candidatas, se divide en llamadas de hasta 25. El contexto de la tabla va completo en cada parte. Las columnas que quedan fuera por el límite registran `skipped_limit`.

### 7.3 Enmascarado semántico (para la IA)

Es una función pura, distinta del enmascarador de F1 (que sigue rigiendo el JSON). Para cada valor, en este orden:

1. Reemplaza las entidades por marcadores, con los validadores y expresiones de la capa 2 y en versión **permisiva**: cualquier texto con forma de RUT es `<RUT>`, aunque su DV sea inválido; correo → `<EMAIL>`; teléfono → `<TELEFONO>`; 13 a 19 dígitos seguidos (con o sin separadores) → `<TARJETA>`; patente → `<PATENTE>`; URL → `<URL>`.
2. Nombres propios → `<NOMBRE>`. Se aplica a toda palabra con mayúscula inicial que no abre la oración, y a toda palabra presente en un diccionario de nombres y apellidos frecuentes en Chile, en cualquier posición y con o sin mayúscula. Ese diccionario se empaqueta en `src/rastro/` y **no puede derivarse de las listas de Faker**: el dataset sintético usa Faker, y un diccionario sacado de ahí haría pasar la prueba de privacidad sin probar nada. Quien construye documenta la fuente pública y su licencia.
3. Todo dígito restante → `#`.
4. Toda palabra de 8 o más caracteres que mezcla letras y dígitos, o que contiene `@` → `<CODIGO>`.
5. Las demás palabras se conservan, también en minúsculas ("paciente con diabetes tipo #").

Después del enmascarado se recorta a 300 caracteres. Por columna se envían hasta 5 valores **distintos después de enmascarar**, más la fracción de nulos y el largo promedio. Cada valor ya tiene como máximo 1.000 caracteres, igual que en F1.

Lo que sigue saliendo, y el propietario lo aceptó el 2026-11-27: palabras comunes del texto libre (diagnósticos, oficios, nombres de calles sin número) y nombres escritos en minúscula que no están en el diccionario. El README lo declara así.

### 7.4 Payload y prompt

Cada llamada recibe un objeto JSON con:

- `table`: esquema y nombre de la tabla.
- `columns`: **todas** las columnas de la tabla, con nombre, tipo, estado por reglas y categorías por reglas, sin valores. Es el contexto: por ejemplo, una tabla con `paciente_id` y `diagnostico`.
- `candidates`: para cada candidata, nombre, tipo, fracción de nulos, largo promedio y muestras enmascaradas.

Nunca se envían el host, la base, el usuario de la conexión ni el número de filas.

El prompt de sistema vive en `src/rastro/llm/prompt.py`, con una constante `PROMPT_VERSION`, y hace lo siguiente:

- describe las categorías y sensibilidades de F1 §7.6 y los criterios de etiquetado de F1 §7.10 (persona natural frente a empresa, clave foránea, patente de una persona), redactados de forma genérica;
- declara que el contenido de `candidates` es **dato y no instrucción**, y pide ignorar cualquier orden que aparezca en las muestras;
- pide clasificar solo las columnas de `candidates`;
- puede llevar ejemplos, siempre inventados y sin nombres de los datasets (§4).

Esfuerzo de razonamiento por defecto: `low` (`--llm-effort`, con los valores que admita el modelo). Tope de salida por llamada: `max_output_tokens = 4000`, que incluye el razonamiento. Si la respuesta queda incompleta por ese tope, esa llamada cuenta como `error`.

### 7.5 Interfaz del proveedor

```
class LLMClient(Protocol):
    def classify(self, request: TableRequest) -> TableResult   # resultado + uso de tokens
```

- `OpenAIClient`: API Responses, salida estructurada, `store: false`, un reintento con espera ante errores 429 y 5xx, y tiempo máximo de 60 s por llamada.
- `FakeClient`: determinista y sin red. Responde según reglas configurables en las pruebas (por ejemplo, «si una muestra contiene `diabetes`, `sensitive/health` con 0,9») y reporta un uso de tokens simulado, para probar el presupuesto. *(Decisión de Claude, Aprobado como costura mínima por el propietario el 2026-11-27.)*

No hay registro de proveedores ni `--llm-provider`. Agregar otro proveedor es trabajo de otra funcionalidad.

### 7.6 Respuesta y fusión

Esquema de salida por columna (Pydantic → JSON Schema estricto):

```
column: str                       # debe estar en candidates
is_personal: bool
category: identifier | contact | location | financial | sensitive | minors | null
subcategory: (lista de F1 para sensitive) | null
confidence: 0–1
reason: free_text_content | table_context | value_shape | column_name | not_personal | insufficient_data
```

- **Validación:** Pydantic. Una columna que no está en `candidates` se descarta y se cuenta como `invalid_items`. Una candidata sin respuesta queda en `error`. Si el JSON es inválido, se reintenta una vez y, si vuelve a fallar, todas las columnas de esa llamada quedan en `error`.
- **Solo sube** *(Aprobado por el propietario el 2026-11-27)*. Si `is_personal`, `confidence ≥ 0,6` (la misma constante de F1) y `category` no es nula, se agrega un `Finding` con `detector: "llm"`, `rule_id: "llm"`, la sensibilidad sacada de la tabla de F1 §7.6 (no la elige el modelo) y `evidence` igual al código `reason`. La columna pasa a `personal`, y a `sensitive: true` si la categoría es `sensitive` o `minors`.
- En cualquier otro caso, el estado no cambia. Si la IA dice que una columna `ambiguous` no es personal, sigue `ambiguous`. *(Decisión de Claude: es conservador y la métrica no cambia, porque `ambiguous` ya cuenta como no detectada.)*
- `evidence` es un código cerrado y nunca texto libre del modelo, así que la respuesta no puede devolver un valor al JSON.

### 7.7 Costo y presupuesto

Precios verificados el 2026-11-27 en la página oficial de precios de OpenAI (nivel Standard, contexto corto ≤ 272K, USD por millón de tokens):

| Modelo | Entrada | Entrada en caché | Salida | Nota |
| --- | --- | --- | --- | --- |
| `gpt-6-luna` | 0,10 | 0,01 | 0,50 | **El más barato vigente.** Razona; esfuerzos `none`, `low`, `medium` (por defecto), `high`, `xhigh` y `max`; con salida estructurada |
| `gpt-5-nano` | 0,05 | 0,005 | 0,40 | **Obsoleto**: OpenAI lo apaga el **2026-12-11** y recomienda `gpt-6-luna` en su lugar |
| `gpt-4o-mini` | 0,15 | 0,075 | 0,60 | Obsoleto: se apaga el 2027-01-14. No razona |
| `gpt-5.4-nano` | 0,20 | 0,02 | 1,25 | Obsoleto: se apaga el 2027-04-01 |
| `gpt-6.1-terra` | 1,00 | 0,05 | 5,00 | Descartado por costo (propietario, 2026-11-27) |

**No hay un modelo más pequeño que `gpt-6-luna` que siga vigente.** El catálogo actual de OpenAI no tiene `mini` ni `nano` de la serie 6: `gpt-6-luna` es el modelo más barato que muestra la página de modelos. Por debajo de su precio solo está `gpt-5-nano`, que se apaga el 2026-12-11. Los modelos pequeños que siguen activos después de esa fecha (`gpt-4o-mini`, `gpt-5.4-nano`) están obsoletos, se apagan entre enero y abril de 2027 y cobran más por token. Por eso la comparación de M3 enfrenta **dos niveles de esfuerzo de `gpt-6-luna`** (§9).

Los tokens de razonamiento se cobran como salida. Sin verificar: si estos modelos aceptan `temperature`; qué niveles de esfuerzo admite `gpt-5-nano` (su página no lo dice); si la página de modelos tiene algo más detrás de su enlace «ver más» (revisé la portada y la página de precios, que no lo muestran). El diseño no depende de `temperature`, porque mide la variación entre corridas.

- **Tabla de precios** en `src/rastro/llm/prices.yml`, con `verified_at`, URL de la fuente y los precios por modelo. Un modelo que no está en la tabla devuelve exit 2: sin precio no hay tope.
- **Estimación previa** (cota superior): por cada llamada, `ceil(caracteres_del_payload / 3)` tokens de entrada más `max_output_tokens` de salida, a precio completo. *(Decisión de Claude: no se agrega un tokenizador como dependencia.)* Si la cota supera `--llm-max-usd`, no se hace ninguna llamada y el escaneo termina con exit 2 y un mensaje que sugiere bajar `--llm-max-columns` o subir el tope.
- **Durante el escaneo:** el costo real sale del `usage` de cada respuesta (entrada, entrada en caché, salida y razonamiento). Antes de cada llamada se comprueba que `gastado + cota de esta llamada ≤ tope`. Si no cabe, la capa se detiene, las candidatas restantes quedan `skipped_budget` y `summary.llm.stopped_by_budget = true`. El escaneo termina con exit 0.
- `--llm-max-usd` por defecto **0,15**. La cota previa de `gpt-6-luna` para el dataset completo es de unos USD 0,13, así que cabe.
- Un error del proveedor (red, 4xx, 5xx tras el reintento) deja esas columnas en `error` y el escaneo sigue. Un 401 (clave inválida) o un 429 por cuota agotada detiene la capa de inmediato. Ningún mensaje incluye la clave ni el payload.

### 7.8 CLI

```
rastro scan ... [--llm] [--llm-model gpt-6-luna] [--llm-effort low]
                [--llm-max-usd 0.15] [--llm-max-columns 300]
                [--llm-dry-run ARCHIVO.jsonl]
```

- `--llm-dry-run` implica `--llm`. Escribe un payload por línea, imprime en la salida de errores la cantidad de candidatas, de llamadas, los tokens estimados y la cota de costo, y no necesita clave, SDK ni red. El JSON del escaneo sale con `settings.llm.dry_run: true` y sin hallazgos `llm`. Sirve también para que el propietario audite exactamente lo que saldría.
- Con `--llm` sin `OPENAI_API_KEY`, o sin el extra instalado: exit 2 con un mensaje en español. Nunca un escaneo silencioso sin IA.
- Modelo por defecto: `gpt-6-luna`, el más barato vigente (§7.7). Esfuerzo por defecto: `low`. *(Decisión de Claude.)*

### 7.9 Contrato JSON (versión `2`)

**Decisión de Claude: sí se sube a `"2"`.** Agregar `llm` al enum `detector` invalida los JSON nuevos frente al JSON Schema v1 publicado, que un consumidor estricto (como F6) validaría, y además se agregan campos con un significado nuevo (`settings.llm`, `summary.llm`, `Column.llm_review`). Subir la versión vuelve explícito ese cambio. F3 subirá a `"3"` con `Recommendation`. `eval/evaluate.py` acepta las versiones 1 y 2.

Cambios respecto de la versión 1:

```
Scan
  schema_version: "2"
  settings.layers: ["name", "pattern"] | ["name", "pattern", "llm"]
  settings.llm: null | {provider: "openai", model, effort, max_usd, max_columns,
                        prompt_version, prices_verified_at, dry_run}
  summary.llm: null | {candidate_columns, sent_columns, calls, failed_calls, invalid_items,
                       upgraded_columns, skipped_budget, skipped_limit,
                       input_tokens, cached_input_tokens, output_tokens, reasoning_tokens,
                       cost_usd, stopped_by_budget, duration_s}

Column
  llm_review: null | {outcome: upgraded | unchanged | error | skipped_budget | skipped_limit,
                      reason (código de §7.6) | null}

Finding
  detector: name | pattern | llm
  evidence: con detector "llm", el código reason; nunca texto del modelo
```

Sin `--llm`, `settings.llm`, `summary.llm` y `llm_review` son `null`, y el resto del JSON es idéntico a la versión 1 salvo `schema_version`. El JSON Schema exportado en `schemas/` se regenera.

### 7.10 Corrección de plurales (N4)

La normalización de la capa 1 prueba el token tal cual y luego sus formas singulares candidatas, en español (`-es` tras consonante, `-s` tras vocal) y en inglés (`-ies` → `-y`, `-es` tras `s`, `x`, `ch` o `sh`, `-s`). Hay coincidencia si alguna forma está en el diccionario. La regla es genérica y tiene pruebas unitarias con plurales regulares y casos que no deben singularizarse. En el mismo lote, *(decisión de Claude)*, se corrigen N7 (el enmascarador de F1 acepta un TLD de una letra y deja literales los valores de un carácter) y N8 (la prueba de privacidad omite los valores que el enmascarado genérico deja iguales). N5 (el mecanismo b de ADR-001 está inerte) se anota en ADR-001 como superado por la capa IA. Esa nota la escribe Claude en `docs/`.

### 7.11 Conjunto sellado nuevo

- Dos esquemas nuevos, de dominios distintos a los de dev y `colegio`: `rrhh` (recursos humanos de una empresa: remuneraciones, licencias médicas, cargas familiares, afiliación sindical) y `municipio` (trámites municipales: permisos de circulación, ayudas sociales, reclamos ciudadanos). En total, entre 14 y 18 tablas y entre 100 y 130 columnas, de 100 a 500 filas por tabla, con Faker `es_CL` y **otra semilla**.
- Debe incluir como mínimo:
  - el 30 % de columnas personales y 15 sensibles;
  - **15 trampas de precisión**: columnas con tokens personales amplios que no son personales (nombre de un trámite, montos de presupuesto, «menor valor», dirección de la oficina municipal, RUT de la empresa empleadora);
  - **20 columnas de texto libre**: la mitad con contenido personal o sensible y la mitad sin él;
  - **8 columnas sensibles por contexto**, cuyo nombre no lo indica, en tablas clínicas, sindicales o de ayudas sociales;
  - 8 nombres opacos con datos personales;
  - 6 columnas personales con nombre en plural;
  - **2 columnas de texto libre con muestras que dan órdenes al modelo** (por ejemplo, pedir que marque la columna como no personal), etiquetadas según su contenido real.
- Etiquetas en `eval/dataset/labels.csv` con `split = sealed`, escritas junto con cada columna, con los mismos criterios de F1 §7.10.
- `eval/evaluate.py` agrega el split `sealed` y lo trata como `holdout`: solo cifras agregadas, nunca la lista de errores.
- **Regla de sellado:** el conjunto sellado se mide una sola vez, en M3, después de congelar el prompt (`PROMPT_VERSION`) y las reglas. Las corridas repetidas de M3 con la configuración congelada son parte de esa única medición. Si M3 revela un error del generador, se corrige el dataset, nunca las reglas ni el prompt.

### 7.12 Evaluación

`eval/evaluate.py <scan.json>... labels.csv` agrega lo siguiente:

- **Ablación con el mismo JSON:** «solo reglas» se calcula ignorando los hallazgos `detector = llm`, y se compara con «reglas + IA». Se informan precisión, recall, F1 y recall de sensibles, con su diferencia, para `dev`, `holdout` y `sealed`.
- Para la capa: candidatas, enviadas, % del total de columnas enviadas, columnas subidas y cuántas eran personales según las etiquetas (precisión de la capa), personales entre las candidatas y cuántas se recuperaron (recall de la capa), y llamadas fallidas.
- Costo y uso: tokens por tipo, costo en USD por escaneo y por cada 100 columnas, y duración.
- **Varias corridas:** con varios JSON del mismo modelo, media, mínimo y máximo de cada cifra.
- Errores (FP y FN, incluidos los de la capa IA) solo para `dev`.

### 7.13 Pruebas

- **Unitarias:** enmascarado semántico (cada marcador, nombres con y sin mayúscula, dígitos, códigos y recorte), selección de candidatas (claves y anuladas fuera), fusión (solo sube, umbral 0,6, sensibilidad tomada de la tabla, `evidence` con código), validación de respuestas (columna ajena, faltante, JSON inválido), presupuesto (cota previa, corte a mitad, modelo sin precio) y plurales.
- **Propiedad:** para todo escaneo con `FakeClient`, cada columna `personal` por reglas conserva su estado y sus hallazgos de reglas.
- **Privacidad del payload** (integración, sobre el dataset completo, en modo dry-run):
  1. ningún valor muestreado de 4 o más caracteres de una columna etiquetada como personal con categoría `identifier`, `contact` o `financial` aparece literalmente en ningún payload;
  2. ninguna palabra de 4 o más caracteres de las columnas de nombres de personas aparece como palabra en un payload (sin distinguir mayúsculas). Si hay choques con palabras comunes, se documenta una lista de excepciones que revisa Claude;
  3. sigue vigente la prueba de privacidad del JSON de F1, ya corregida por N8.
- **Clave:** con un valor centinela en `OPENAI_API_KEY` y `FakeClient`, el centinela no aparece en la salida estándar, en la salida de errores ni en el JSON, ni siquiera ante un error simulado del proveedor.
- **Sin `--llm`:** una prueba comprueba que el módulo `openai` no se importa y que no hay sockets abiertos hacia afuera.
- **CI:** solo `FakeClient`, sin secretos.
- Con `--llm` y `gpt-6-luna`, el escaneo del dataset completo termina en menos de 10 minutos (se verifica en M3, no en CI).

## 8. Estructura propuesta

```
src/rastro/llm/
  __init__.py
  candidates.py        # §7.2
  masking.py           # enmascarado semántico §7.3
  names/               # diccionario de nombres y apellidos (fuente pública, no Faker)
  payload.py           # §7.4
  prompt.py            # prompt de sistema + PROMPT_VERSION
  client.py            # LLMClient, TableRequest, TableResult
  openai_client.py     # import perezoso de openai
  fake_client.py
  budget.py            # estimación, seguimiento y corte
  prices.yml
  layer.py             # orquesta y fusiona (§7.6)
src/rastro/models.py   # contrato v2
eval/dataset/          # generador + split sealed
eval/evaluate.py       # ablación, sealed, varias corridas
```

## 9. Condición para el plan

**Lotes y aislamiento** *(decisión de Claude)*:

- **Lote 0:** contrato v2, JSON Schema y lectura de v1 y v2 en `evaluate.py`, más el split `sealed` en la evaluación.
- **Lote 1:** plurales (N4), N7 y N8 (§7.10). Lo sigue el hito **H1, línea base «solo reglas» de F2**: escaneo y evaluación de `dev` y de `colegio` (solo agregados). Luego Claude corre un `--llm-dry-run` del dataset y recalcula el presupuesto de §9 con los tokens estimados reales.
- **Lote 2, dos encargos en paralelo en worktrees separados:**
  - **2A, capa IA:** §7.1 a §7.9 y §7.12 a §7.13, con `FakeClient` y el cliente OpenAI. No lee §7.11.
  - **2B, conjunto sellado:** lee solo F1 §7.6, los criterios de etiquetado de F1 §7.10 y §7.11 de este spec. Nunca lee `src/rastro/llm/`, las reglas ni el prompt.
- **Hito H2, ajuste del prompt solo con `dev`:** como máximo 3 corridas pagadas con `gpt-6-luna`, mirando solo los errores de dev. Los cambios del prompt los hace Codex en un encargo de ajuste. Al terminar se congela `PROMPT_VERSION`.
- **2B se revisa e integra solo después de congelar el prompt.** Así, ni Codex ni Claude ven el conjunto sellado mientras el prompt todavía puede cambiar.
- **M3, medición final:** la matriz de modelos de abajo, sobre `dev`, `holdout` y `sealed`. Luego Claude actualiza el README: cifras, % enviado, costo por escaneo, qué sale hacia OpenAI y la remisión a sus condiciones de uso, sin afirmaciones legales.

**Presupuesto para USD 4 de crédito** (estimación previa, que H1 recalcula con el dry-run): unas 460 columnas en total, unas 250 candidatas, unas 60 llamadas, unos 2.000 tokens de entrada y hasta unos 1.500 de salida por llamada con esfuerzo `low`, es decir unos 120K de entrada y 90K de salida por escaneo completo.

**Matriz de M3** (no hay un modelo más pequeño vigente, §7.7): `gpt-6-luna` con esfuerzo `none` (sin razonamiento, el más barato) frente a `gpt-6-luna` con esfuerzo `low` (el valor por defecto), 3 corridas cada uno. Así se mide si razonar vale lo que cuesta. Si M3 se hace antes del 2026-12-11, se agregan 3 corridas de `gpt-5-nano` como referencia histórica.

| Uso | Corridas | Costo esperado | Tope por corrida |
| --- | --- | --- | --- |
| Prueba de la clave (una tabla) | 1 | < USD 0,01 | 0,05 |
| H2, ajuste en dev con `gpt-6-luna` `low` | ≤ 3 | ~USD 0,03 c/u | 0,15 |
| M3, `gpt-6-luna` `none` | 3 | ~USD 0,02 c/u | 0,15 |
| M3, `gpt-6-luna` `low` | 3 | ~USD 0,06 c/u | 0,15 |
| M3, `gpt-5-nano` (solo antes del 2026-12-11) | 3 | ~USD 0,04 c/u | 0,15 |
| **Total sin nano / con nano** | | **~USD 0,35 / ~USD 0,50** | |

**Tope acumulado de F2: USD 1,50 de gasto real**, sumado desde `summary.llm.cost_usd` de cada corrida. Claude lleva la cuenta en la nota de M3 y se detiene si la próxima corrida pudiera superarlo. Los topes por corrida solo acotan el peor caso. El crédito de USD 4 queda con al menos USD 2,50 libres.

## 10. Decisiones tomadas

| Decisión | Quién | Estado |
| --- | --- | --- |
| Solo OpenAI como proveedor real; sin Anthropic | Propietario | **Aprobado** el 2026-11-27 |
| Costura mínima `LLMClient` con `FakeClient` para pruebas | Claude | **Aprobado** el 2026-11-27 (el propietario la recomendó como costura mínima) |
| Crédito total USD 4; implementación sin gasto; medición real en M3 | Propietario | **Aprobado** el 2026-11-27 |
| Candidatas: `ambiguous` + `not_personal` sin señal, agrupadas por tabla | Propietario | **Aprobado** el 2026-11-27 |
| La IA solo sube; nunca baja un hallazgo de reglas | Propietario | **Aprobado** el 2026-11-27 |
| Enmascarado semántico; salen palabras comunes y nunca identificadores; `--llm-dry-run`; prueba de privacidad del payload | Propietario | **Aprobado** el 2026-11-27 |
| Opt-in con `--llm`; clave solo por `OPENAI_API_KEY` | Propietario | **Aprobado** el 2026-11-27 |
| Conjunto sellado nuevo con trampas de precisión, medido una sola vez | Propietario | **Aprobado** el 2026-11-27 |
| N4 en un lote inicial, medido como línea base «solo reglas» | Propietario | **Aprobado** el 2026-11-27 |
| `schema_version` "2" (§7.9) | Claude | **Propuesto** |
| Anuladas y claves fuera de las candidatas; `ambiguous` sigue `ambiguous` si la IA dice no (§7.2, §7.6) | Claude | **Propuesto** |
| `evidence` como código cerrado; sensibilidad tomada de la tabla de F1 | Claude | **Propuesto** |
| Topes: USD 0,15 por escaneo y USD 1,50 acumulado en F2; 300 columnas; 4.000 tokens de salida por llamada; esfuerzo `low` | Claude | **Propuesto** |
| Estimación por caracteres sin tokenizador | Claude | **Propuesto** |
| N7 y N8 en el lote 1 | Claude | **Propuesto** |
| Conjunto sellado: `rrhh` y `municipio`; 2B se integra tras congelar el prompt | Claude | **Propuesto** |
| Sin `gpt-6.1-terra` ni `sol`: un modelo barato junto con luna | Propietario | **Aprobado** el 2026-11-27 |
| Modelo por defecto `gpt-6-luna`; M3 compara `none` con `low`, más `gpt-5-nano` si M3 se hace antes del 2026-12-11 | Claude | **Propuesto** (no hay un modelo más pequeño vigente, §7.7) |

## 11. Lo que queda a quien construye

- El texto del prompt y sus ejemplos, dentro de §7.4 y §4.
- Las expresiones del enmascarado permisivo y la fuente del diccionario de nombres, dentro de §7.3.
- El nombre exacto de los parámetros del SDK `openai` (salida estructurada, `store`, esfuerzo, `max_output_tokens`), verificado en su documentación vigente.
- Las tablas y columnas del conjunto sellado, dentro de §7.11.
- Los mensajes de consola, en español y sin valores ni clave.

## 12. Preguntas abiertas para el propietario

No queda ninguna pregunta que bloquee el plan. Para aprobar el spec, el propietario confirma lo siguiente:

1. **Corrección de los modelos en la hoja de ruta.** El criterio de «terminada» de F2 (y la fila de §10 de F1) nombra `gpt-5-nano`, que se apaga el 2026-12-11. Propuesta de texto: «costo por escaneo para `gpt-6-luna` con esfuerzo `none` y `low` (y `gpt-5-nano` si M3 se hace antes del 2026-12-11)». La redacta Claude cuando el propietario dé el sí.
2. *(Opcional, no bloquea.)* Una sola corrida de `gpt-4o-mini` (unos USD 0,03, sin razonamiento, se apaga el 2027-01-14) como segundo modelo de otra generación. Recomendación: no incluirla, porque es un modelo obsoleto y la comparación de esfuerzos de luna responde mejor la pregunta.

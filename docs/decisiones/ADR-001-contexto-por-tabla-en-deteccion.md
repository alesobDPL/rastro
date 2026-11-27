# ADR-001 · Contexto de tabla en la capa de nombre: roles de persona y salud por tabla

[Decisiones](README.md) · [Inicio](../00-inicio.md)

**Estado:** Aprobado (2026-11-27). Redactado por el subagente Opus; aprobado por el propietario junto con la aceptación de E7.

## Contexto

La línea base de F1 (M1) mostró dos clases de falsos negativos que no se corrigen ampliando el diccionario:

1. **Personas en tablas con nombre de organización.** El spec (§7.4) anula los hallazgos `identifier` y `contact` cuando el nombre de la columna **o de la tabla** contiene un token de organización (`proveedor`, `sucursal`, `soporte`…). Eso evita marcar el RUT o el teléfono de una empresa, pero también apaga a las personas que viven en esas tablas: el ejecutivo de un proveedor, el agente de soporte, quien retira en una sucursal.
2. **Salud que solo se deduce de la tabla.** En una tabla de eventos clínicos (cirugías, recetas, vacunaciones…), columnas de nombre neutro (duración, muestra, producto aplicado) son datos de salud del paciente. La capa de nombre hoy solo mira tokens de la columna.

Restricciones: no cambiar ninguna firma de la Task 2 ni el contrato JSON; reglas en YAML y genéricas (§4 y §9 del spec); `sensitive` y `minors` nunca se anulan.

## Decisión

Se agregan dos mecanismos generales a la capa de nombre (`name_rules.py` y `detect.py`), con sus listas en los YAML de `rules/`:

- **(a) El rol de persona prevalece sobre la organización de la tabla.** Si el token de organización está **solo en el nombre de la tabla** y la columna contiene un token de rol o marca de persona (por ejemplo agente, ejecutivo, titular, responsable, representante, particular), esa anulación no actúa, en ninguna de las dos capas. Un token de organización en la **columna** sigue anulando siempre, y las anulaciones por metadato y por sufijo (`id`, `codigo`) no cambian.
- **(b) Reglas de salud por tabla.** Si el nombre de la tabla contiene un token inequívoco de evento clínico y no contiene un token de organización, cada columna sin hallazgo propio que no sea técnica (claves, códigos, folios, números de serie o lote, marcas de auditoría o fechas de sistema) recibe un hallazgo `sensitive`/`health` de la capa de nombre, con `rule_id` que empieza con `name.`, confianza fija y como evidencia los tokens de la tabla (metadato).

Esto **precisa §7.4 del spec**: la frase "el nombre de la columna o de la tabla contiene un token de organización" pasa a leerse con la excepción (a), y la capa de nombre puede usar el nombre de la tabla para emitir hallazgos (b). El spec no se edita; esta ADR es la referencia.

## Alternativas consideradas

- **Quitar tokens de organización de la lista:** recupera a esas personas, pero vuelve a marcar el RUT y el teléfono de las empresas y contradice §7.4.
- **Reglas solo de columna con más vocabulario:** no alcanza las columnas de nombre neutro en tablas clínicas y empuja a parches por nombre de columna.
- **Dejarlo para la capa IA (F2):** posible, pero son patrones deterministas y baratos; la IA queda para el texto libre y los nombres opacos.

## Consecuencias

- Sube la exhaustividad en personas y, sobre todo, en datos sensibles, sin tocar el contrato.
- Riesgo de precisión en (b): como `sensitive` no se anula, un token de tabla ambiguo o una columna técnica no excluida produce un falso positivo que nada apaga. Se mitiga con tokens de evento clínico inequívocos, la exclusión de tablas con token de organización y de columnas técnicas, y pruebas de contraste.
- Riesgo en (a): un token de rol demasiado amplio reactivaría el RUT o el correo de la propia organización; la lista de roles debe denotar personas.
- La capa de nombre deja de depender solo del nombre de la columna; F3 (riesgo) y F2 (IA) deben tenerlo en cuenta.

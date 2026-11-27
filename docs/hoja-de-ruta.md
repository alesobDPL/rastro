# Hoja de ruta · rastro

[Volver al inicio](00-inicio.md)

Estado: **Aprobado** por el propietario el 2026-11-27 (propuesta del 2026-11-26). Claude la escribe al aprobar el diseño del MVP y el propietario la aprueba. Dice **qué** se construye y en qué orden, sin detalle de implementación: cada funcionalidad tiene su propio spec y plan justo antes de implementarse.

Enfoque elegido por el propietario el 2026-11-26: **medir primero**. La primera funcionalidad ya entrega precisión y recall contra un dataset etiquetado; cada funcionalidad siguiente muestra su efecto en esas cifras.

## Funcionalidades

| #   | Funcionalidad                                                                                                                       | Depende de | Terminada cuando                                                                                                                                                                                                              | Estado    | Spec · Plan · Rama                                                                                            |
| --- | ----------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------- |
| F1  | Escaneo Postgres medible: dataset sintético etiquetado, detección por nombre y por patrón, enmascarador, salida JSON y evaluación   | —          | Con la BD sintética levantada en Docker, el propietario ejecuta `rastro scan` y un comando de evaluación: obtiene el JSON del inventario y un resumen con precisión y recall, y ningún valor real de la BD aparece en el JSON | en main   | [spec](superpowers/specs/2026-11-26-escaneo-postgres-medible-design.md) · [plan](superpowers/plans/2026-11-27-escaneo-postgres-medible.md) · `feat/escaneo-postgres-medible` |
| F2  | Capa IA con OpenAI: columnas ambiguas con `--llm`, muestras enmascaradas, costo por escaneo y comparación de modelos                | F1         | Con `--llm` y su clave, las columnas ambiguas reciben categoría y confianza; la evaluación muestra cuánto mejora el recall, el % de columnas enviadas a la IA y el costo, para `gpt-6-luna` con esfuerzo `none` y `low` (y `gpt-5-nano` si M3 se hace antes del 2026-12-11)                    | diseño aprobado (2026-11-27) | [spec](superpowers/specs/2026-11-27-capa-ia-design.md)                                                                                                             |
| F3  | Reportes HTML, Markdown y CSV con puntaje de riesgo, recomendaciones y marcas de falso positivo en `rastro.yml`                     | F1         | El propietario abre el reporte HTML del dataset y ve el inventario por tabla y columna, el riesgo y qué hacer; una columna marcada "no es dato personal" en `rastro.yml` no reaparece en el siguiente escaneo                 | pendiente | —                                                                                                             |
| F4  | Soporte MySQL                                                                                                                       | F1         | El mismo dataset cargado en MySQL da un inventario equivalente al de Postgres                                                                                                                                                 | pendiente | —                                                                                                             |
| F5  | Escaneo de código con Semgrep: datos personales en logs y envío a SDKs de terceros                                                  | F1         | `rastro scan-code <repo>` sobre un repo de ejemplo encuentra los casos sembrados y aparece en el reporte                                                                                                                      | pendiente | —                                                                                                             |
| F6  | Privacy CI: GitHub Action que comenta en el PR cuando una migración `.sql` agrega una columna con datos personales sin clasificar   | F1, F3     | En un repo de demostración, un PR con `diagnostico_mascota TEXT` recibe el comentario del bot y la verificación falla o advierte según la configuración                                                                       | pendiente | —                                                                                                             |
| F7  | Publicación: paquete en PyPI (nombre de distribución por decidir, propuesta `rastro-cl`), imagen Docker, README con métricas y demo | F1–F6      | `pip install` del paquete publicado funciona en una máquina limpia y el README muestra las métricas medidas y la demo                                                                                                         | pendiente | —                                                                                                             |

<!-- Estados: pendiente | diseño | plan | en curso | integrada | en main | descartada.
     "integrada": todos sus lotes están en la rama de la funcionalidad; "en main": solo tras el merge autorizado.
     Una funcionalidad activa a la vez (diseño, plan o en curso), salvo que el propietario apruebe otra cosa.
     Claude actualiza el Estado y los enlaces al cambiar de fase. -->

## Fuera del MVP

- Panel web multiusuario.
- Conectores MongoDB y BigQuery.
- Plantilla de evaluación de impacto y generación de política de privacidad.
- Migraciones de Django, Alembic u otros ORM en Privacy CI (el MVP reconoce solo `.sql`).
- Otros proveedores de IA (Claude, Ollama local).
- Muestreo aleatorio de filas (`TABLESAMPLE`) en lugar de las primeras N filas.

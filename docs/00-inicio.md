# rastro

Copiloto local de cumplimiento de la Ley 21.719: inventaria los datos personales de una base de datos y un repositorio, los clasifica por sensibilidad y recomienda acciones, sin que los datos salgan del servidor.

## Estado actual · actualizado 2026-11-27

- **Fase:** implementación
- **Funcionalidad activa:** F1 Escaneo Postgres medible (spec: [aprobado 2026-11-27](superpowers/specs/2026-11-26-escaneo-postgres-medible-design.md) · plan: [aprobado 2026-11-27](superpowers/plans/2026-11-27-escaneo-postgres-medible.md) · rama: `feat/escaneo-postgres-medible`)
- **Lote en curso:** lotes 0, 1, 2 y 3 (E1–E7) integrados en `feat/escaneo-postgres-medible` (248 pruebas, ruff OK). ADR-001 Aprobado (2026-11-27). Falta M2 y la revisión final.
- **Último avance:** lote 3 (E7) aceptado e integrado. Dev: precisión 0.978, exhaustividad 0.777, sensibles 0.407 (línea base M1: 0.875 / 0.625 / 0.259). Holdout sin medir aún.
- **Bloqueos:** ninguno.
- **Siguiente paso:** M2: Sonnet mide dev y holdout sobre la rama integrada y escribe el README (documentando el texto libre y los nombres opacos como límite de F1 y motivo de F2); después, revisión final de la rama por el subagente Opus.
- **Última bitácora:** ninguna todavía.

| Encargo | Lote | Estado | Siguiente paso |
| --- | --- | --- | --- |
| E1 esqueleto y contrato | 0 | integrado | — |
| E2 detección | 1 | integrado | — |
| E3 dataset | 1 | integrado | — |
| E4 conector y enmascarador | 1 | integrado | — |
| E5 escáner y CLI | 2 | integrado | — |
| E6 evaluación | 2 | integrado | — |
| E7 ajuste de detección | 3 | integrado | M2 |

<!-- Fases: descubrimiento | diseño | plan | implementación | revisión | despliegue.
     Este bloque es el índice; el detalle de cada encargo vive en su Seguimiento (docs/privado/encargos/).
     Mantenerlo en unas 20 líneas. Repo público: si es público, sin datos sensibles aquí. -->

## Mapa de la documentación

| Carpeta | Contenido | ¿Va a GitHub? |
| --- | --- | --- |
| [hoja-de-ruta.md](hoja-de-ruta.md) | Funcionalidades en orden, con su estado: cuánto falta para terminar | Sí |
| [arquitectura/](arquitectura/README.md) | Visión general, convenciones y [criterios de desarrollo](arquitectura/criterios-desarrollo.md) | Sí |
| [decisiones/](decisiones/README.md) | Un ADR por decisión de arquitectura | Sí |
| [superpowers/specs/](superpowers/specs/README.md) | Diseños (brainstorming) | Sí |
| [superpowers/plans/](superpowers/plans/README.md) | Planes de implementación con lotes (writing-plans) | Sí |
| [privado/](privado/README.md) | Bitácora, encargos y sus ejecuciones, pruebas, infraestructura y producto | No: repo git propio |

## Estado de las decisiones

- **Pendiente:** no hay decisión; no usarla como requisito.
- **Propuesto:** alternativa presentada, sin aprobación.
- **Aprobado:** acuerdo explícito del propietario, con fecha y contexto.

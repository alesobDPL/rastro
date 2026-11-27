# rastro

Copiloto local de cumplimiento de la Ley 21.719: inventaria los datos personales de una base de datos y un repositorio, los clasifica por sensibilidad y recomienda acciones, sin que los datos salgan del servidor.

## Estado actual · actualizado 2026-11-27

- **Fase:** implementación
- **Funcionalidad activa:** F1 Escaneo Postgres medible (spec: [aprobado 2026-11-27](superpowers/specs/2026-11-26-escaneo-postgres-medible-design.md) · plan: [aprobado 2026-11-27](superpowers/plans/2026-11-27-escaneo-postgres-medible.md) · rama: `feat/escaneo-postgres-medible`)
- **Lote en curso:** lote 1 (E2, E3, E4) entregado y auditado
- **Último avance:** E2, E3 y E4 entregados por Codex y auditados por Claude (94, 16 y 33 pruebas en verde; ruff OK); Claude recomienda aceptar los tres.
- **Bloqueos:** ninguno.
- **Siguiente paso:** propietario: aceptar o devolver E2, E3 y E4. Luego Claude: integrar el lote 1 y delegar al subagente Opus los encargos del lote 2 (T5, T6).
- **Última bitácora:** ninguna todavía.

| Encargo | Lote | Estado | Siguiente paso |
| --- | --- | --- | --- |
| E1 esqueleto y contrato | 0 | integrado | — |
| E2 detección | 1 | entregado, auditado | Propietario: aceptar o devolver |
| E3 dataset | 1 | entregado, auditado | Propietario: aceptar o devolver |
| E4 conector y enmascarador | 1 | entregado, auditado | Propietario: aceptar o devolver |

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

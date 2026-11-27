# rastro

Copiloto local de cumplimiento de la Ley 21.719: inventaria los datos personales de una base de datos y un repositorio, los clasifica por sensibilidad y recomienda acciones, sin que los datos salgan del servidor.

## Estado actual · actualizado 2026-11-27

- **Fase:** implementación
- **Funcionalidad activa:** F1 Escaneo Postgres medible (spec: [aprobado 2026-11-27](superpowers/specs/2026-11-26-escaneo-postgres-medible-design.md) · plan: [aprobado 2026-11-27](superpowers/plans/2026-11-27-escaneo-postgres-medible.md) · rama: `feat/escaneo-postgres-medible`)
- **Lote en curso:** lote 0 (E1), entregado y auditado
- **Último avance:** E1 (lote 0) entregado por Codex y auditado por Claude: 8 pruebas, ruff y compose en verde; Claude recomienda aceptar.
- **Bloqueos:** ninguno.
- **Siguiente paso:** propietario: aceptar o devolver E1. Luego Claude: integrar el lote 0 y delegar al subagente Opus los encargos del lote 1 (T2, T3, T4).
- **Última bitácora:** ninguna todavía.

| Encargo | Lote | Estado | Siguiente paso |
| --- | --- | --- | --- |
| E1 esqueleto y contrato | 0 | entregado, auditado | Propietario: aceptar o devolver |

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

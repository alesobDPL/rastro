# rastro

Copiloto local de cumplimiento de la Ley 21.719: inventaria los datos personales de una base de datos y un repositorio, los clasifica por sensibilidad y recomienda acciones, sin que los datos salgan del servidor.

## Estado actual · actualizado 2026-11-27

- **Fase:** F1 terminada y en `main` (merge local 2026-11-27, sin push); F2 por diseñar
- **Funcionalidad activa:** ninguna. F1 Escaneo Postgres medible integrada en `main` (rama `feat/escaneo-postgres-medible`, conservada).
- **Lote en curso:** ninguno. Lotes 0–3 (E1–E7), M2 y revisión final hechos; 248 pruebas, ruff OK.
- **Último avance:** merge de F1 a `main` autorizado por el propietario (2026-11-27). Dev: 0.978 / 0.777 / sensibles 0.407; holdout: 0.923 / 0.585 / 0.321. Deuda no bloqueante en `docs/privado/fases-y-pruebas/revision-final-escaneo-postgres-medible.md`.
- **Bloqueos:** ninguno.
- **Siguiente paso:** propietario: decidir si hace push de `main`, si se lanza un encargo corto para N1–N3 (validación de `--sample-size`, `connect_timeout`, error de `-o`) y cuándo se diseña F2 (recordar clave de OpenAI y límite de gasto).
- **Última bitácora:** ninguna todavía.

| Encargo | Lote | Estado | Siguiente paso |
| --- | --- | --- | --- |
| E1 esqueleto y contrato | 0 | integrado | — |
| E2 detección | 1 | integrado | — |
| E3 dataset | 1 | integrado | — |
| E4 conector y enmascarador | 1 | integrado | — |
| E5 escáner y CLI | 2 | integrado | — |
| E6 evaluación | 2 | integrado | — |
| E7 ajuste de detección | 3 | integrado | — |

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

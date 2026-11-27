# rastro

Copiloto local de cumplimiento de la Ley 21.719: inventaria los datos personales de una base de datos y un repositorio, los clasifica por sensibilidad y recomienda acciones, sin que los datos salgan del servidor.

## Estado actual · actualizado 2026-11-27

- **Fase:** F1 terminada y en `main` (push a origin, 2026-11-27); E8 (N1–N3) integrado en `feat/endurecer-cli-escaneo` (sin merge a `main`); F2 con spec **Propuesto**.
- **Funcionalidad activa:** ninguna. Endurecimiento del CLI (E8) en `feat/endurecer-cli-escaneo`: `--sample-size` ≥ 1, `connect_timeout` 10 s por defecto, validación de `-o`.
- **Lote en curso:** ninguno. E1–E8 integrados; 262 pruebas, ruff OK en la rama.
- **Último avance:** E8 aceptado por el propietario e integrado (2026-11-27). Spec F2 (capa IA, solo OpenAI, tope USD 1,50 acumulado) escrito por Opus, pendiente de aprobación.
- **Bloqueos:** ninguno.
- **Siguiente paso:** propietario: aprobar el spec F2 (`superpowers/specs/2026-11-27-capa-ia-design.md`) y la corrección de la hoja de ruta; decidir el merge de `feat/endurecer-cli-escaneo` a `main`. Luego: plan de F2 (Opus). La clave de OpenAI solo se pide cuando haga falta, por variable de entorno.
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
| E8 endurecer CLI (N1–N3) | Mant. 1 | integrado | merge a `main` con el sí del propietario |

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

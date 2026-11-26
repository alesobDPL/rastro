# Criterios de alcance, calidad y proceso

[Volver al inicio](../00-inicio.md)

Estado: **Propuesto** el 2026-11-26. Rige el proceso una vez aprobado; no aprueba ningún diseño ni plan.

## Alcance controlado

- Construir un MVP pequeño, funcional, mantenible y con calidad profesional, centrado en completar el flujo principal.
- Incluir solo las funcionalidades necesarias para ese flujo; evitar funcionalidades especulativas y sobreingeniería.
- Posponer excepciones poco frecuentes cuando exista una solución sencilla y segura. Simplificar el alcance no reduce los controles de calidad ni de seguridad.
- Documentar las funcionalidades futuras sin implementarlas ni anticipar sus mecanismos técnicos.

## Calidad de ingeniería

- Arquitectura clara y adecuada al tamaño del proyecto.
- Código limpio, organizado y tipado cuando corresponda.
- Validaciones en el frontend y en el backend.
- Autenticación y autorización correctamente implementadas.
- Manejo adecuado de errores y estados inesperados.
- Integridad de datos y seguridad frente a concurrencia cuando sea relevante.
- Pruebas automatizadas de las reglas de negocio críticas, y pruebas de integración y end-to-end de los flujos principales.
- Configuración segura y despliegue reproducible.

## Descubrimiento eficiente

- Priorizar las preguntas que pueden cambiar el alcance, la arquitectura o decisiones principales, preferentemente una por mensaje.
- Registrar los detalles menores, las excepciones y las funcionalidades futuras como Pendientes o Propuestas, y continuar.
- Ante alternativas relevantes, presentar ventajas, desventajas y una recomendación.

## Etapas

1. Brainstorming → diseño en `superpowers/specs/` → aprobación explícita.
2. writing-plans → plan en `superpowers/plans/` con tabla de lotes → aprobación explícita.
3. Implementación por Codex en lotes de hasta 3 encargos en paralelo, cada uno en su rama, con TDD, depuración sistemática y verificación antes de entregar.
4. Auditoría de Claude Code por encargo y aceptación del propietario.
5. Integración del lote en la rama de la funcionalidad y pruebas del conjunto; al final, revisión de toda la rama y merge a `main` con el sí del propietario.

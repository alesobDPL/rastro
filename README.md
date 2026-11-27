# rastro

Copiloto local de cumplimiento de la Ley 21.719 (Chile). Inventaría los datos personales de una base de datos PostgreSQL, los clasifica por sensibilidad y entrega un reporte, **sin que los datos salgan de tu máquina**: todo corre en local y los valores de las muestras nunca se guardan en el reporte.

> **Estado: F1, escaneo de Postgres medible.** Esta versión escanea el esquema y una muestra de cada columna con reglas por nombre y por patrón. No usa IA, no escanea repositorios de código y todavía no recomienda acciones. Ver [hoja de ruta](docs/hoja-de-ruta.md).

## Qué hace hoy

- Lista las tablas y columnas de uno o varios esquemas.
- Lee una muestra pequeña de cada columna (las primeras 50 filas por defecto, con consultas de solo lectura).
- Clasifica cada columna como **personal**, **ambigua** o **no personal**, con su categoría (identificador, contacto, financiero, salud, etc.), una confianza y los detectores que la respaldan.
- Escribe un reporte JSON (contrato v1, [esquema](schemas/scan-v1.schema.json)) donde los valores quedan enmascarados.
- Incluye un dataset sintético etiquetado y un evaluador para medir la calidad de la detección con precisión y exhaustividad.

## Instalación

Requiere Python 3.11 o superior y Docker (solo para la base de desarrollo).

```powershell
pip install -e ".[dev]"
docker compose up -d db
```

La base de desarrollo queda en `localhost:54329` con credenciales ficticias; copia `.env.example` a `.env` si quieres cambiar la URL.

## Uso

```powershell
# Escanear una base y guardar el reporte
rastro scan postgresql://usuario:clave@host:5432/base -o reporte.json

# Opciones útiles
rastro scan --schema ventas --schema clientes --exclude-table "ventas.log_*" --sample-size 100
```

La URL también puede venir de la variable `RASTRO_DB_URL`. El progreso sale por la salida de errores; el reporte JSON se escribe en el archivo de `-o` o, si se omite, en la salida estándar. `--exclude-table` acepta patrones tipo glob sobre `esquema.tabla`.

## Medir la calidad

El repositorio trae un dataset sintético con tres esquemas, 350 columnas etiquetadas junto con su definición y datos generados con Faker (semilla fija 21719):

- `veterinaria` y `ecommerce` (**dev**, 280 columnas): sirven para ajustar las reglas.
- `colegio` (**holdout**, 70 columnas): no se usa para ajustar nada; solo mide si las mejoras generalizan.

```powershell
python -m eval.dataset.load
rastro scan -o eval/results/scan.json
python eval/evaluate.py eval/results/scan.json eval/dataset/labels.csv
```

Una columna cuenta como detectada solo si queda como *personal*; *ambigua* cuenta como no detectada.

### Resultados (2026-11-27)

| | dev antes | dev después | holdout antes | holdout después |
| --- | --- | --- | --- | --- |
| Precisión | 0,875 | **0,978** | 0,889 | **0,923** |
| Exhaustividad (recall) | 0,625 | **0,777** | 0,585 | **0,585** |
| F1 | 0,729 | **0,866** | 0,706 | **0,716** |
| Exhaustividad en datos sensibles | 0,259 | **0,407** | 0,321 | **0,321** |

«Antes» es la línea base con las reglas del primer lote; «después», con la ronda de ajuste hecha mirando solo `dev`.

**Cómo leerlos con honestidad.** La mejora en `dev` es real, pero en gran parte es específica de ese vocabulario: en `holdout`, que no se tocó, la exhaustividad y la exhaustividad en sensibles no cambiaron, y solo mejoró la precisión (un falso positivo menos). La cifra que mejor estima el desempeño sobre una base desconocida es la de `holdout`: **un 58 % de las columnas personales y un 32 % de las sensibles**. Con 70 columnas, además, cada columna mueve las cifras más de un punto. Son datos sintéticos; no equivalen a una base real.

## Límites conocidos de esta versión

Rastro F1 no puede, con reglas, detectar bien dos tipos de columna. Son un límite documentado y el motivo de la fase siguiente:

- **Texto libre con datos personales dentro** (observaciones, notas de consulta, relatos, mensajes). El nombre de la columna no lo delata y el contenido es heterogéneo. Estas columnas se marcan **ambiguas** (revisar a mano); no se afirma que contengan datos personales.
- **Nombres de columna opacos o abreviados** (códigos internos, siglas, nombres sin relación con su contenido) cuando el contenido no calza con un patrón.
- Los datos **sensibles** (salud, etc.) dependen casi por completo del nombre de la columna; por eso su exhaustividad es la más baja.
- La muestra son las primeras filas, no una muestra aleatoria.

La fase **F2** agrega una capa de IA para clasificar el texto libre y los nombres opacos, con un diseño de enmascarado propio para no enviar datos personales.

## Documentación

- [Estado y mapa del proyecto](docs/00-inicio.md)
- [Arquitectura](docs/arquitectura/README.md) · [decisiones (ADR)](docs/decisiones/README.md)
- [Diseño de F1](docs/superpowers/specs/2026-11-26-escaneo-postgres-medible-design.md)

## Desarrollo

```powershell
pytest          # las pruebas de integración necesitan la base levantada y RASTRO_TEST_DB_URL
ruff check .
```

Rastro se desarrolla con agentes de IA bajo dirección y aprobación humana; las reglas están en [AGENTS.md](AGENTS.md).

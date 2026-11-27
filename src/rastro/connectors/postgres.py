import json
from collections.abc import Sequence
from fnmatch import fnmatchcase

import psycopg
from sqlalchemy import Connection, Engine, bindparam, column, create_engine, make_url, select, text
from sqlalchemy import table as sql_table
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.sql import quoted_name

from rastro.connectors.types import (
    ColumnInfo,
    ConnectionFailed,
    SchemaNotFound,
    TableInfo,
    TableReadError,
    TableSample,
)
from rastro.models import Source

_SCHEMAS = text("SELECT nspname FROM pg_catalog.pg_namespace")

_CATALOG = text("""
    SELECT n.nspname AS schema_name,
           c.relname AS table_name,
           c.reltuples,
           a.attname AS column_name,
           pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
           NOT (a.attnotnull OR t.typnotnull) AS nullable,
           t.typcategory = 'S' AS is_text,
           (t.typcategory IN ('S', 'N') OR t.oid IN (
               'pg_catalog.json'::pg_catalog.regtype,
               'pg_catalog.jsonb'::pg_catalog.regtype
           )) AS sampled
    FROM pg_catalog.pg_namespace AS n
    JOIN pg_catalog.pg_class AS c ON c.relnamespace = n.oid
    LEFT JOIN pg_catalog.pg_attribute AS a
        ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
    LEFT JOIN pg_catalog.pg_type AS t ON t.oid = a.atttypid
    WHERE c.relkind IN ('r', 'p') AND NOT c.relispartition
      AND n.nspname IN :schemas
    ORDER BY n.nspname, c.relname, a.attnum
""").bindparams(bindparam("schemas", expanding=True))


def table_read_error(exc: psycopg.Error | None) -> TableReadError:
    sqlstate = exc.sqlstate if exc is not None else None
    if sqlstate == "42501":
        return TableReadError("permiso denegado al leer la tabla")
    if sqlstate == "57014":
        return TableReadError("la consulta superó el tiempo máximo")
    return TableReadError(f"error al leer la tabla (código {sqlstate or 'desconocido'})")


class PostgresConnector:
    def __init__(self, url: str, *, statement_timeout_ms: int = 30000) -> None:
        try:
            parsed_url = make_url(url).set(drivername="postgresql+psycopg")
            self._engine = create_engine(
                parsed_url,
                connect_args={
                    "options": f"-c default_transaction_read_only=on "
                    f"-c statement_timeout={int(statement_timeout_ms)}"
                },
                hide_parameters=True,
                logging_name=__name__,
                pool_logging_name=__name__,
            )
        except (SQLAlchemyError, ValueError):
            raise ConnectionFailed() from None
        # El motor y el pool pueden registrar muestras y errores del driver.
        self._engine.logger.disabled = True
        self._engine.pool.logger.disabled = True

    @property
    def engine(self) -> Engine:
        return self._engine

    def source(self) -> Source:
        url = self.engine.url
        return Source(
            engine="postgresql",
            host=url.host,
            port=url.port,
            database=url.database or "",
            user=url.username or "",
        )

    def _connect(self) -> Connection:
        try:
            return self.engine.connect()
        except (SQLAlchemyError, psycopg.Error, ValueError):
            raise ConnectionFailed() from None

    def list_tables(
        self, schemas: Sequence[str] = (), exclude: Sequence[str] = ()
    ) -> list[TableInfo]:
        tables: dict[tuple[str, str], TableInfo] = {}
        try:
            with self._connect() as connection:
                existing = set(connection.scalars(_SCHEMAS))
                if schemas:
                    for schema in schemas:
                        if schema not in existing:
                            raise SchemaNotFound(schema)
                    selected = list(schemas)
                else:
                    selected = [
                        schema
                        for schema in existing
                        if schema not in {"pg_catalog", "information_schema"}
                        and not schema.startswith("pg_toast")
                    ]

                for row in connection.execute(_CATALOG, {"schemas": selected}):
                    qualified_name = f"{row.schema_name}.{row.table_name}"
                    if any(fnmatchcase(qualified_name, pattern) for pattern in exclude):
                        continue

                    key = (row.schema_name, row.table_name)
                    if key not in tables:
                        estimate = int(row.reltuples) if row.reltuples >= 0 else None
                        tables[key] = TableInfo(row.schema_name, row.table_name, estimate, [])
                    if row.column_name is not None:
                        tables[key].columns.append(
                            ColumnInfo(
                                row.column_name,
                                row.data_type,
                                row.nullable,
                                row.sampled,
                                row.is_text,
                            )
                        )
        except (SQLAlchemyError, psycopg.Error, ValueError):
            raise ConnectionFailed() from None
        return list(tables.values())

    def sample(self, table: TableInfo, n: int) -> TableSample:
        names = [info.name for info in table.columns if info.sampled]
        if not names:
            return TableSample(rows=0, values={})

        relation = sql_table(
            quoted_name(table.name, True),
            *(column(quoted_name(name, True)) for name in names),
            schema=quoted_name(table.schema, True),
        )
        values: dict[str, list[str | None]] = {name: [] for name in names}
        rows = 0
        try:
            with self._connect() as connection:
                for row in connection.execute(select(*relation.c).limit(n)):
                    rows += 1
                    for name, value in zip(names, row, strict=True):
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value, ensure_ascii=False)
                        values[name].append(None if value is None else str(value)[:1000])
        except (SQLAlchemyError, psycopg.Error, TypeError, ValueError, RecursionError) as exc:
            original = exc.orig if isinstance(exc, DBAPIError) else exc
            driver_error = original if isinstance(original, psycopg.Error) else None
            raise table_read_error(driver_error) from None
        return TableSample(rows=rows, values=values)

    def close(self) -> None:
        self.engine.dispose()

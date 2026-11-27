import argparse
import os

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from eval.dataset.build import DEFAULT_SEED, TableSpec, build_dataset

_LOAD_ERROR = "No se pudo cargar el dataset en PostgreSQL."


def _load_table(cursor: psycopg.Cursor, name: sql.Identifier, table: TableSpec) -> None:
    definitions = sql.SQL(", ").join(
        sql.SQL("{} {}").format(sql.Identifier(column.name), sql.SQL(column.sql_type))
        for column in table.columns
    )
    cursor.execute(sql.SQL("CREATE TABLE {} ({})").format(name, definitions))

    rows = (
        tuple(
            Jsonb(value) if column.sql_type == "jsonb" and value is not None else value
            for column, value in zip(table.columns, row, strict=True)
        )
        for row in table.rows
    )
    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in table.columns)
    cursor.executemany(sql.SQL("INSERT INTO {} VALUES ({})").format(name, placeholders), rows)


def load_dataset(url: str, seed: int = DEFAULT_SEED) -> None:
    dataset = build_dataset(seed)
    try:
        with psycopg.connect(url) as connection, connection.cursor() as cursor:
            tables = []
            for schema in dataset.schemas:
                name = sql.Identifier(schema.name)
                cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(name))
                cursor.execute(sql.SQL("CREATE SCHEMA {}").format(name))
                for table in schema.tables:
                    qualified_name = sql.Identifier(schema.name, table.name)
                    _load_table(cursor, qualified_name, table)
                    tables.append(qualified_name)
            cursor.execute(sql.SQL("ANALYZE {}").format(sql.SQL(", ").join(tables)))
    except psycopg.Error:
        raise RuntimeError(_LOAD_ERROR) from None


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, "Argumentos inválidos. Usa --help para consultar las opciones.\n")


def _main() -> None:
    parser = _ArgumentParser(
        prog="python -m eval.dataset.load",
        description="Recrea los esquemas del dataset sintético en PostgreSQL.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="Muestra esta ayuda.")
    parser.add_argument("--url", metavar="URL", help="URL de conexión. Por defecto, RASTRO_DB_URL.")
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, metavar="N", help="Semilla del dataset."
    )
    args = parser.parse_args()
    url = args.url if args.url is not None else os.environ.get("RASTRO_DB_URL")
    if not url:
        parser.exit(2, "Indica --url o define RASTRO_DB_URL.\n")

    try:
        load_dataset(url, args.seed)
    except RuntimeError:
        parser.exit(1, f"{_LOAD_ERROR}\n")


if __name__ == "__main__":
    _main()

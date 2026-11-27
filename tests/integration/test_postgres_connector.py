import logging
import traceback
from collections.abc import Iterator

import psycopg
import pytest
from sqlalchemy import make_url, text
from sqlalchemy.exc import DBAPIError

from rastro.connectors.postgres import PostgresConnector
from rastro.connectors.types import (
    ColumnInfo,
    Connector,
    SchemaNotFound,
    TableReadError,
    TableSample,
)

pytestmark = pytest.mark.integration

SCHEMA = "rastro_test_conn"
READER = "rastro_test_reader"
READER_PASSWORD = "lector_ficticio_4"


@pytest.fixture
def admin(pg_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(pg_url, autocommit=True) as connection:
        connection.execute("CREATE SCHEMA rastro_test_conn")
        try:
            yield connection
        finally:
            connection.execute("DROP SCHEMA rastro_test_conn CASCADE")


@pytest.fixture
def connector(pg_url: str, admin: psycopg.Connection) -> Iterator[PostgresConnector]:
    connector = PostgresConnector(pg_url)
    try:
        yield connector
    finally:
        connector.close()


@pytest.fixture
def reader(pg_url: str, admin: psycopg.Connection) -> Iterator[PostgresConnector]:
    reader_url = make_url(pg_url).set(username=READER, password=READER_PASSWORD)
    admin.execute("CREATE ROLE rastro_test_reader LOGIN PASSWORD 'lector_ficticio_4'")
    try:
        admin.execute("GRANT USAGE ON SCHEMA rastro_test_conn TO rastro_test_reader")
        connector = PostgresConnector(reader_url.render_as_string(hide_password=False))
        try:
            yield connector
        finally:
            connector.close()
    finally:
        try:
            admin.execute("DROP OWNED BY rastro_test_reader")
        finally:
            admin.execute("DROP ROLE rastro_test_reader")


def test_lists_tables_and_types(admin: psycopg.Connection, connector: PostgresConnector) -> None:
    admin.execute("""
        CREATE TABLE rastro_test_conn.types (
            description text NOT NULL, quantity integer, payload jsonb, since date, token uuid
        )
    """)
    admin.execute("CREATE TABLE rastro_test_conn.partitioned (id integer) PARTITION BY RANGE (id)")
    admin.execute("""
        CREATE TABLE rastro_test_conn.child PARTITION OF rastro_test_conn.partitioned
        FOR VALUES FROM (0) TO (10)
    """)
    admin.execute("CREATE VIEW rastro_test_conn.types_view AS SELECT * FROM rastro_test_conn.types")

    partitioned, types = connector.list_tables(schemas=[SCHEMA])

    assert isinstance(connector, Connector)
    assert (partitioned.name, types.name) == ("partitioned", "types")
    assert types.schema == SCHEMA
    assert types.estimated_rows is None
    assert types.columns == [
        ColumnInfo("description", "text", False, True, True),
        ColumnInfo("quantity", "integer", True, True, False),
        ColumnInfo("payload", "jsonb", True, True, False),
        ColumnInfo("since", "date", True, False, False),
        ColumnInfo("token", "uuid", True, False, False),
    ]


def test_sample_limit_and_json(
    admin: psycopg.Connection, connector: PostgresConnector, caplog: pytest.LogCaptureFixture
) -> None:
    admin.execute("CREATE TABLE rastro_test_conn.records (body text, payload jsonb, since date)")
    admin.execute("""
        INSERT INTO rastro_test_conn.records
        SELECT repeat('a', 1500), '{"city": "Ñuñoa"}'::jsonb, NULL
        FROM generate_series(1, 10)
    """)
    table, = connector.list_tables(schemas=[SCHEMA])

    with caplog.at_level(logging.DEBUG, logger="sqlalchemy.engine"):
        sample = connector.sample(table, 5)

    assert sample.rows == 5
    assert sample.values == {"body": ["a" * 1000] * 5, "payload": ['{"city": "Ñuñoa"}'] * 5}
    assert "Ñuñoa" not in caplog.text
    assert "Ñuñoa" not in repr(sample)


def test_read_only_session(connector: PostgresConnector) -> None:
    with connector.engine.connect() as connection:
        assert connection.execute(text("SHOW statement_timeout")).scalar_one() == "30s"
        with pytest.raises(DBAPIError) as caught:
            connection.execute(text("CREATE TABLE rastro_test_conn.x(i int)"))

    assert isinstance(caught.value.orig, psycopg.errors.ReadOnlySqlTransaction)


def test_permission_denied_table(admin: psycopg.Connection, reader: PostgresConnector) -> None:
    admin.execute("CREATE TABLE rastro_test_conn.allowed (id integer)")
    admin.execute("CREATE TABLE rastro_test_conn.denied (id integer)")
    admin.execute("CREATE TABLE rastro_test_conn.unsampled (since date)")
    admin.execute("GRANT SELECT ON rastro_test_conn.allowed TO rastro_test_reader")

    allowed, denied, unsampled = reader.list_tables(schemas=[SCHEMA])

    assert (allowed.name, denied.name, unsampled.name) == ("allowed", "denied", "unsampled")
    assert reader.source().user == READER
    assert READER_PASSWORD not in reader.source().model_dump_json()
    assert reader.sample(unsampled, 5) == TableSample(rows=0, values={})
    with pytest.raises(TableReadError) as caught:
        reader.sample(denied, 5)

    assert str(caught.value) == "permiso denegado al leer la tabla"
    assert "psycopg.errors.InsufficientPrivilege" not in "".join(
        traceback.format_exception(caught.value)
    )


def test_odd_identifiers(admin: psycopg.Connection, connector: PostgresConnector) -> None:
    admin.execute('''
        CREATE TABLE rastro_test_conn."Tabla Rara" (
            "Nombre Completo" text, "select" integer, "col""comilla" text
        )
    ''')
    admin.execute('INSERT INTO rastro_test_conn."Tabla Rara" VALUES (%s, %s, %s)', ("Ana", 7, None))

    table, = connector.list_tables(schemas=[SCHEMA])

    assert table.name == "Tabla Rara"
    assert connector.sample(table, 1) == TableSample(
        rows=1, values={"Nombre Completo": ["Ana"], "select": ["7"], 'col"comilla': [None]}
    )


def test_unknown_schema(connector: PostgresConnector) -> None:
    with pytest.raises(SchemaNotFound, match="no_existe"):
        connector.list_tables(schemas=["no_existe"])


def test_exclude_glob(admin: psycopg.Connection, connector: PostgresConnector) -> None:
    admin.execute("CREATE TABLE rastro_test_conn.tmp_a (id integer)")
    admin.execute('CREATE TABLE rastro_test_conn."Tmp_a" (id integer)')
    admin.execute("CREATE TABLE rastro_test_conn.records (id integer)")

    tables = connector.list_tables(exclude=["rastro_test_conn.tmp_*"])

    assert {table.name for table in tables if table.schema == SCHEMA} == {"Tmp_a", "records"}
    assert all(
        table.schema not in {"pg_catalog", "information_schema"}
        and not table.schema.startswith("pg_toast")
        for table in tables
    )

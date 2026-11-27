import traceback

import psycopg
import pytest
from psycopg import errors

from rastro.connectors.postgres import PostgresConnector, table_read_error
from rastro.connectors.types import ConnectionFailed, TableReadError


@pytest.mark.parametrize(
    ("error_type", "expected"),
    [
        (errors.InsufficientPrivilege, "permiso denegado al leer la tabla"),
        (errors.QueryCanceled, "la consulta superó el tiempo máximo"),
        (errors.InvalidTextRepresentation, "error al leer la tabla (código 22P02)"),
    ],
)
def test_table_read_error_hides_original_message(
    error_type: type[psycopg.Error], expected: str
) -> None:
    error = table_read_error(error_type("valor-secreto-123"))

    assert isinstance(error, TableReadError)
    assert str(error) == expected
    assert "valor-secreto-123" not in repr(error)


def test_connection_failed_hides_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PGCONNECT_TIMEOUT", "3")
    url = "postgresql://u:Clave_Secreta_9@127.0.0.1:1/db"
    with pytest.raises(ConnectionFailed) as caught:
        connector = PostgresConnector(url)
        try:
            connector.list_tables()
        finally:
            connector.close()

    assert "Clave_Secreta_9" not in str(caught.value)
    assert "Clave_Secreta_9" not in repr(caught.value)
    assert "Clave_Secreta_9" not in "".join(traceback.format_exception(caught.value))

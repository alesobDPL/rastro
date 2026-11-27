from unittest.mock import Mock

import psycopg
import pytest
from typer.testing import CliRunner

from rastro import cli
from rastro.connectors.types import SchemaNotFound

runner = CliRunner()


def test_cli_missing_url_exit_2(monkeypatch):
    monkeypatch.delenv("RASTRO_DB_URL", raising=False)

    result = runner.invoke(cli.app, ["scan"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Falta la URL de PostgreSQL" in result.stderr


@pytest.mark.parametrize("url", ["mysql://u:p@h/db", "PostgreSQL://u:p@h/db", "postgresql:db"])
def test_cli_non_postgres_exit_2(url, monkeypatch):
    connector = Mock()
    monkeypatch.setattr(cli, "PostgresConnector", connector, raising=False)

    result = runner.invoke(cli.app, ["scan", url])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "La URL debe comenzar con" in result.stderr
    assert url not in result.stderr
    connector.assert_not_called()


def test_cli_connection_failure_hides_password(monkeypatch):
    url = "postgresql://u:Clave_Secreta_9@127.0.0.1:1/db"
    connect = Mock(side_effect=psycopg.OperationalError(f"Conexión fallida: {url}"))
    monkeypatch.setattr(psycopg, "connect", connect)

    result = runner.invoke(cli.app, ["scan", url])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No se pudo conectar a PostgreSQL" in result.stderr
    assert "Clave_Secreta_9" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    connect.assert_called_once()


@pytest.mark.parametrize(("failure", "message"), [
    (SchemaNotFound("Clave_Secreta_9"), "No existe uno de los esquemas solicitados"),
    (RuntimeError("Clave_Secreta_9"), "Ocurrió un error inesperado durante el escaneo"),
])
def test_cli_scan_failure_closes_connector(monkeypatch, failure, message):
    connector = Mock()
    connector.list_tables.side_effect = failure
    factory = Mock(return_value=connector)
    monkeypatch.setattr(cli, "PostgresConnector", factory, raising=False)
    monkeypatch.setenv("RASTRO_DB_URL", "postgresql://u:p@localhost/env")
    url = "postgres://u:Clave_Secreta_9@localhost/arg"

    result = runner.invoke(cli.app, ["scan", url, "--schema", "faltante"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert message in result.stderr
    assert "Clave_Secreta_9" not in result.stdout + result.stderr
    factory.assert_called_once_with(url)
    connector.close.assert_called_once_with()


def test_cli_invalid_arguments_hide_url():
    url = "postgresql://u:Clave_Secreta_9@localhost/db"

    result = runner.invoke(cli.app, ["scan", "--sample-size", url])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Argumentos inválidos" in result.stderr
    assert "Clave_Secreta_9" not in result.stderr

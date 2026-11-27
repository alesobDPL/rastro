from pathlib import Path
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


@pytest.mark.parametrize("sample_size", ["0", "-1"])
def test_cli_rejects_nonpositive_sample_size(monkeypatch, sample_size):
    factory = Mock()
    monkeypatch.setattr(cli, "PostgresConnector", factory)

    result = runner.invoke(
        cli.app, ["scan", "postgresql://u:p@localhost/db", "--sample-size", sample_size]
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == "Argumentos inválidos. Consulta rastro scan --help.\n"
    factory.assert_not_called()


@pytest.fixture
def simulated_scan(monkeypatch):
    factory = Mock()
    run_scan = Mock()
    run_scan.return_value.to_json.return_value = '{"tablas": []}'
    monkeypatch.setattr(cli, "PostgresConnector", factory)
    monkeypatch.setattr(cli, "run_scan", run_scan)
    return factory, run_scan


def test_cli_accepts_minimum_sample_size(simulated_scan):
    _, run_scan = simulated_scan

    result = runner.invoke(cli.app, ["scan", "postgresql://u:p@localhost/db", "--sample-size", "1"])

    assert result.exit_code == 0
    assert result.stdout == '{"tablas": []}\n'
    run_scan.assert_called_once()
    request = run_scan.call_args.args[1]
    assert isinstance(request, cli.ScanRequest)
    assert request.sample_size == 1


@pytest.mark.parametrize("parent_is_file", [False, True])
def test_cli_rejects_invalid_output_parent(monkeypatch, tmp_path, parent_is_file):
    parent = tmp_path / "no"
    if parent_is_file:
        parent.touch()
    factory = Mock()
    monkeypatch.setattr(cli, "PostgresConnector", factory)

    result = runner.invoke(
        cli.app, ["scan", "postgresql://u:p@localhost/db", "-o", str(parent / "x.json")]
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        "La carpeta del archivo de salida no existe. Créala antes de escanear.\n"
    )
    factory.assert_not_called()
    assert parent.exists() == parent_is_file


def test_cli_rejects_directory_as_output(monkeypatch, tmp_path):
    factory = Mock()
    monkeypatch.setattr(cli, "PostgresConnector", factory)

    result = runner.invoke(cli.app, ["scan", "postgresql://u:p@localhost/db", "-o", str(tmp_path)])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == "La ruta de salida es una carpeta; indica un archivo.\n"
    factory.assert_not_called()


def test_cli_reports_write_failure(monkeypatch, tmp_path, simulated_scan):
    factory, _ = simulated_scan
    monkeypatch.setattr(Path, "write_text", Mock(side_effect=PermissionError("Clave_Secreta_9")))

    result = runner.invoke(
        cli.app, ["scan", "postgresql://u:p@localhost/db", "-o", str(tmp_path / "x.json")]
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "No se pudo escribir el archivo de salida.\n"
    factory.return_value.close.assert_called_once_with()


def test_cli_reports_scan_oserror_as_unexpected(tmp_path, simulated_scan):
    _, run_scan = simulated_scan
    run_scan.side_effect = OSError("Clave_Secreta_9")
    output = tmp_path / "x.json"

    result = runner.invoke(cli.app, ["scan", "postgresql://u:p@localhost/db", "-o", str(output)])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Ocurrió un error inesperado durante el escaneo.\n"
    assert not output.exists()


def test_cli_writes_report_to_output(tmp_path, simulated_scan):
    output = tmp_path / "x.json"

    result = runner.invoke(cli.app, ["scan", "postgresql://u:p@localhost/db", "-o", str(output)])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert output.read_text(encoding="utf-8") == '{"tablas": []}\n'

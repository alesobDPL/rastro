from pathlib import Path
from typing import Annotated, NoReturn

import typer
from typer.core import TyperCommand

from rastro.connectors.postgres import PostgresConnector
from rastro.connectors.types import ConnectionFailed, SchemaNotFound
from rastro.scanner import ScanRequest, run_scan

try:
    from typer._click.exceptions import UsageError
except ImportError:
    from click import UsageError


def _exit_with_error(message: str, code: int) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(code) from None


class _ScanCommand(TyperCommand):
    def parse_args(self, ctx: typer.Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except UsageError:
            _exit_with_error("Argumentos inválidos. Consulta rastro scan --help.", 2)


app = typer.Typer(pretty_exceptions_enable=False)


@app.callback()
def main() -> None:
    """Herramienta de escaneo de bases de datos PostgreSQL."""


@app.command(cls=_ScanCommand)
def scan(
    url: Annotated[str | None, typer.Argument(envvar="RASTRO_DB_URL", metavar="URL")] = None,
    output: Annotated[Path | None, typer.Option("-o", metavar="ARCHIVO")] = None,
    schema: Annotated[list[str] | None, typer.Option("--schema", metavar="NOMBRE")] = None,
    exclude_table: Annotated[
        list[str] | None, typer.Option("--exclude-table", metavar="PATRÓN")
    ] = None,
    sample_size: Annotated[int, typer.Option("--sample-size")] = 50,
) -> None:
    """Escanea una base de datos PostgreSQL."""
    if not url:
        _exit_with_error("Falta la URL de PostgreSQL. Usa el argumento URL o RASTRO_DB_URL.", 2)
    if not url.startswith(("postgresql://", "postgres://")):
        _exit_with_error("La URL debe comenzar con postgresql:// o postgres://.", 2)

    request = ScanRequest(
        sample_size=sample_size, schemas=schema or [], exclude_tables=exclude_table or []
    )
    try:
        connector = PostgresConnector(url)
        try:
            result = run_scan(connector, request, lambda message: typer.echo(message, err=True))
        finally:
            connector.close()

        text = result.to_json()
        if output is None:
            typer.echo(text)
        else:
            output.write_text(text + "\n", encoding="utf-8")
    except ConnectionFailed:
        _exit_with_error("No se pudo conectar a PostgreSQL.", 1)
    except SchemaNotFound:
        _exit_with_error("No existe uno de los esquemas solicitados.", 1)
    except Exception:
        _exit_with_error("Ocurrió un error inesperado durante el escaneo.", 1)

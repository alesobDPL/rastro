import typer

app = typer.Typer()


@app.callback()
def main() -> None:
    """Herramienta de escaneo de bases de datos PostgreSQL."""


@app.command()
def scan() -> None:
    """Escanea una base de datos PostgreSQL (pendiente de implementación)."""

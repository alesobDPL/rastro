from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from rastro.models import Source


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool
    sampled: bool
    is_text: bool


@dataclass
class TableInfo:
    schema: str
    name: str
    estimated_rows: int | None
    columns: list[ColumnInfo]


@dataclass
class TableSample:
    rows: int
    values: dict[str, list[str | None]] = field(repr=False)


class ConnectionFailed(Exception):
    def __init__(self) -> None:
        super().__init__("no se pudo abrir la sesión de PostgreSQL")


class SchemaNotFound(Exception):
    def __init__(self, schema: str) -> None:
        super().__init__(f"no existe el esquema {schema!r}")


class TableReadError(Exception):
    pass


@runtime_checkable
class Connector(Protocol):
    def source(self) -> Source: ...

    def list_tables(
        self, schemas: Sequence[str] = (), exclude: Sequence[str] = ()
    ) -> list[TableInfo]: ...

    def sample(self, table: TableInfo, n: int) -> TableSample: ...

    def close(self) -> None: ...

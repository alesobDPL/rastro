from collections.abc import Sequence
from datetime import UTC

from rastro import __version__
from rastro.connectors.types import ColumnInfo, Connector, TableInfo, TableReadError, TableSample
from rastro.models import Detector, Scan, Source
from rastro.scanner import ScanRequest, run_scan


class MemoryConnector:
    def __init__(self, *tables: tuple[TableInfo, TableSample | TableReadError]) -> None:
        self.tables = [table for table, _ in tables]
        self.samples = {(table.schema, table.name): sample for table, sample in tables}
        self.list_args: tuple[Sequence[str], Sequence[str]] | None = None
        self.sample_calls: list[tuple[str, int]] = []
        self.closed = False

    def source(self) -> Source:
        return Source(engine="postgresql", host=None, port=None, database="pruebas", user="lector")

    def list_tables(
        self, schemas: Sequence[str] = (), exclude: Sequence[str] = ()
    ) -> list[TableInfo]:
        self.list_args = (schemas, exclude)
        return self.tables

    def sample(self, table: TableInfo, n: int) -> TableSample:
        self.sample_calls.append((table.name, n))
        sample = self.samples[table.schema, table.name]
        if isinstance(sample, TableReadError):
            raise sample
        return sample

    def close(self) -> None:
        self.closed = True


def text_column(name: str, *, sampled: bool = True) -> ColumnInfo:
    return ColumnInfo(name, "text", True, sampled, True)


def test_scan_builds_contract():
    connector = MemoryConnector(
        (
            TableInfo("public", "contactos", 12, [text_column("email"), text_column("notas")]),
            TableSample(1, {"email": ["persona@example.test"], "notas": ["Texto de ejemplo"]}),
        ),
        (
            TableInfo("public", "fichas", 8, [text_column("diagnostico", sampled=False)]),
            TableSample(0, {}),
        ),
    )
    assert isinstance(connector, Connector)
    settings = ScanRequest(sample_size=7, schemas=["public"], exclude_tables=["public.tmp_*"])
    progress: list[str] = []

    scan = run_scan(connector, settings, progress.append)

    assert Scan.from_json(scan.to_json()) == scan
    assert scan.schema_version == "1"
    assert scan.rastro_version == __version__
    assert scan.started_at.tzinfo is UTC and scan.finished_at.tzinfo is UTC
    assert scan.started_at <= scan.finished_at
    assert scan.source == connector.source()
    assert scan.summary.model_dump() == {
        "tables": 2, "columns": 3, "personal": 2, "sensitive": 1, "ambiguous": 1,
        "failed_tables": 0,
    }
    assert scan.settings.model_dump() == {
        "sample_size": 7, "schemas": ["public"], "excluded_tables": ["public.tmp_*"],
        "layers": ["name", "pattern"],
    }
    assert connector.list_args == (["public"], ["public.tmp_*"])
    assert connector.sample_calls == [("contactos", 7)]
    assert not connector.closed
    assert scan.tables[0].estimated_rows == 12
    assert scan.tables[1].columns[0].masked_samples == []
    assert scan.tables[1].columns[0].null_ratio is None
    assert scan.tables[1].columns[0].findings
    assert any("public.contactos" in message for message in progress)
    assert "persona@example.test" not in "\n".join(progress)


def test_scan_request_defaults_are_independent():
    request = ScanRequest()
    request.schemas.append("public")
    request.exclude_tables.append("public.tmp_*")

    assert ScanRequest().sample_size == 50
    assert ScanRequest().schemas == []
    assert ScanRequest().exclude_tables == []


def test_masked_samples_and_evidence():
    ruts = [
        "12.345.678-5", "13.457.890-4", "21.598.628-4", "10.000.000-8",
        "16.777.451-2", "9.876.543-3",
    ]
    values = [None, "", ruts[0], ruts[0], *ruts[1:]]
    connector = MemoryConnector((
        TableInfo("public", "registros", None, [text_column("dato")]),
        TableSample(len(values), {"dato": values}),
    ))

    scan = run_scan(connector, ScanRequest())

    column = scan.tables[0].columns[0]
    assert column.status == "personal"
    assert column.masked_samples == ["1*.***.***-5", "1*.***.***-4", "2*.***.***-4"]
    assert [(finding.detector, finding.evidence) for finding in column.findings] == [
        (Detector.PATTERN, "1*.***.***-5"),
    ]
    assert all(rut not in scan.to_json() for rut in ruts)


def test_failed_table_continues():
    message = "sin permisos para leer la tabla"
    connector = MemoryConnector(
        (TableInfo("public", "cerrada", None, [text_column("email")]), TableReadError(message)),
        (
            TableInfo("public", "abierta", None, [text_column("dato")]),
            TableSample(1, {"dato": ["ejemplo"]}),
        ),
    )

    scan = run_scan(connector, ScanRequest())

    failed, complete = scan.tables
    assert failed.error == message
    assert failed.sampled_rows == 0
    column = failed.columns[0]
    assert column.null_ratio is None
    assert column.masked_samples == []
    assert column.status == "personal"
    assert [(finding.detector, finding.evidence) for finding in column.findings] == [
        (Detector.NAME, "email"),
    ]
    assert complete.error is None and complete.sampled_rows == 1
    assert complete.columns[0].masked_samples == ["e******"]
    assert scan.summary.failed_tables == 1


def test_empty_and_null_columns():
    connector = MemoryConnector(
        (TableInfo("public", "vacia", 0, [text_column("dato")]), TableSample(0, {"dato": []})),
        (
            TableInfo("public", "escasa", 3, [text_column("dato"), text_column("auxiliar")]),
            TableSample(3, {
                "dato": [None, None, None],
                "auxiliar": ["uno@example.test", "dos@example.test", "tres@example.test"],
            }),
        ),
    )

    scan = run_scan(connector, ScanRequest())

    empty, sparse = scan.tables
    null, few = sparse.columns
    assert empty.columns[0].null_ratio is None
    assert null.null_ratio == 1.0
    assert few.null_ratio == 0.0
    assert empty.columns[0].masked_samples == null.masked_samples == []
    assert all(
        finding.detector != Detector.PATTERN
        for column in (empty.columns[0], null, few)
        for finding in column.findings
    )


def test_suppressed_propagated():
    connector = MemoryConnector((
        TableInfo("public", "registros", None, [text_column("email_empresa")]),
        TableSample(1, {"email_empresa": ["ventas@example.test"]}),
    ))

    scan = run_scan(connector, ScanRequest())

    column = scan.tables[0].columns[0]
    assert column.findings == []
    assert len(column.suppressed) == 1
    suppression = column.suppressed[0]
    assert suppression.detector == Detector.NAME
    assert suppression.rule_id and "empresa" in suppression.context

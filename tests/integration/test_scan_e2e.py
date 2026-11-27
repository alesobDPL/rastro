from collections.abc import Iterator
from time import perf_counter
from urllib.parse import unquote, urlsplit

import pytest
from typer.testing import CliRunner

from eval.dataset.build import DEFAULT_SEED, Dataset, build_dataset
from eval.dataset.load import load_dataset
from rastro.cli import app
from rastro.detection.detect import detect_column
from rastro.masking import mask
from rastro.models import Detector, Scan, ValueKind

pytestmark = pytest.mark.integration
runner = CliRunner()


@pytest.fixture(scope="module")
def dataset(pg_url):
    load_dataset(pg_url, DEFAULT_SEED)
    return build_dataset(DEFAULT_SEED)


@pytest.fixture(scope="module")
def scan_output(pg_url, dataset, tmp_path_factory):
    destination = tmp_path_factory.mktemp("rastro") / "scan.json"
    started = perf_counter()
    result = runner.invoke(app, ["scan", pg_url, "-o", str(destination)])
    return result, destination, perf_counter() - started


def test_scan_dataset_e2e(scan_output, dataset):
    result, destination, elapsed = scan_output

    assert result.exit_code == 0
    assert result.stdout == ""
    scan = Scan.from_json(destination.read_text(encoding="utf-8"))
    schemas = {table.schema_name for table in scan.tables}
    assert {schema.name for schema in dataset.schemas} <= schemas
    assert scan.summary.failed_tables == 0
    assert elapsed < 120


def _contract_terms(schema: dict) -> set[str]:
    terms = set(schema.get("properties", {}))
    terms.update(value for value in schema.get("enum", []) if isinstance(value, str))
    constant = schema.get("const")
    if isinstance(constant, str):
        terms.add(constant)
    for child in schema.values():
        if isinstance(child, dict):
            terms.update(_contract_terms(child))
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, dict):
                    terms.update(_contract_terms(item))
    return terms


def _scalar_leaves(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for child in value.values():
            yield from _scalar_leaves(child)
    elif isinstance(value, list):
        for child in value:
            yield from _scalar_leaves(child)
    else:
        yield str(value)


def _jsonb_leaves(dataset: Dataset) -> Iterator[str]:
    for schema in dataset.schemas:
        for table in schema.tables:
            for row in table.rows:
                for value in row:
                    if isinstance(value, (dict, list)):
                        yield from _scalar_leaves(value)


def _without_dataset_metadata(scan: Scan, dataset: Dataset, stderr: str) -> tuple[Scan, str]:
    columns_by_table = {
        (schema.name, table.name): {column.name for column in table.columns}
        for schema in dataset.schemas
        for table in schema.tables
    }
    scan = scan.model_copy(deep=True)
    progress_lines = {}
    for index, table in enumerate(scan.tables, start=1):
        table_key = (table.schema_name, table.name)
        if table_key not in columns_by_table:
            continue

        count = f"({index}/{len(scan.tables)})"
        progress_lines[f"Escaneando {table.schema_name}.{table.name} {count}"] = (
            f"Escaneando {count}"
        )
        for column in table.columns:
            if column.name not in columns_by_table[table_key]:
                continue
            # La evidencia de nombre forma parte de los metadatos del contrato.
            name_detection = detect_column(table=table.name, column=column.name, samples=[])
            name_evidence = {
                (item.rule_id, item.raw_evidence) for item in name_detection.detections
            }
            for finding in column.findings:
                if (
                    finding.detector == Detector.NAME
                    and (finding.rule_id, finding.evidence) in name_evidence
                ):
                    finding.evidence = ""
            column.name = ""
        table.schema_name = table.name = ""

    stderr = "\n".join(progress_lines.get(line, line) for line in stderr.splitlines())
    return scan, stderr


def test_privacy_no_raw_values(scan_output, dataset):
    result, destination, _ = scan_output
    assert result.exit_code == 0
    text = destination.read_text(encoding="utf-8")
    scan = Scan.from_json(text)
    excluded = _contract_terms(Scan.model_json_schema(by_alias=True))
    for schema in dataset.schemas:
        excluded.add(schema.name)
        for table in schema.tables:
            excluded.add(table.name)
            excluded.update(column.name for column in table.columns)

    payload, stderr = _without_dataset_metadata(scan, dataset, result.stderr)
    evidence = []
    for table in payload.tables:
        for column in table.columns:
            evidence.extend(column.masked_samples)
            evidence.extend(finding.evidence for finding in column.findings)

    values = set(dataset.iter_values()) | set(_jsonb_leaves(dataset))
    output = (payload.to_json(), result.stdout, stderr)
    leaks = 0
    for value in values:
        if len(value) < 4 or value in excluded or mask(value, ValueKind.GENERIC) == value:
            continue
        haystacks = evidence if value.isdigit() and len(value) < 6 else output
        leaks += any(value in haystack for haystack in haystacks)
    if leaks:
        pytest.fail(f"Se encontraron {leaks} valores sin enmascarar", pytrace=False)


def test_password_not_in_output(pg_url, scan_output):
    result, destination, _ = scan_output
    assert result.exit_code == 0
    password = urlsplit(pg_url).password
    if password:
        outputs = (destination.read_text(encoding="utf-8"), result.stdout, result.stderr)
        if any(raw in output for raw in {password, unquote(password)} for output in outputs):
            pytest.fail("La contraseña aparece en la salida", pytrace=False)

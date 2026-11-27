from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import islice

from rastro import __version__
from rastro.connectors.types import ColumnInfo, Connector, TableReadError, TableSample
from rastro.detection.classify import classify_column
from rastro.detection.detect import Detection, detect_column
from rastro.masking import mask
from rastro.models import (
    Column,
    Detector,
    Finding,
    Scan,
    Settings,
    Status,
    Summary,
    Suppression,
    Table,
    ValueKind,
)


@dataclass
class ScanRequest:
    sample_size: int = 50
    schemas: list[str] = field(default_factory=list)
    exclude_tables: list[str] = field(default_factory=list)


def _to_finding(detection: Detection) -> Finding:
    evidence = detection.raw_evidence
    if detection.detector == Detector.PATTERN:
        evidence = mask(evidence, detection.kind or ValueKind.GENERIC)
    return Finding(
        category=detection.category,
        subcategory=detection.subcategory,
        sensitivity=detection.sensitivity,
        confidence=detection.confidence,
        detector=detection.detector,
        rule_id=detection.rule_id,
        evidence=evidence,
    )


def _scan_column(table_name: str, info: ColumnInfo, sample: TableSample) -> Column:
    sampled_rows = sample.rows if info.sampled else 0
    values = sample.values.get(info.name, []) if sampled_rows else []
    detection = detect_column(table=table_name, column=info.name, samples=values)
    verdict = classify_column(
        detection.detections, column=info.name, is_text=info.is_text, samples=values
    )
    strongest_pattern = max(
        (item for item in detection.detections if item.detector == Detector.PATTERN),
        key=lambda item: item.confidence,
        default=None,
    )
    pattern_kind = strongest_pattern.kind if strongest_pattern else None
    sample_kind = pattern_kind or ValueKind.GENERIC
    distinct_values = dict.fromkeys(value for value in values if value and value.strip())
    return Column(
        name=info.name,
        data_type=info.data_type,
        nullable=info.nullable,
        null_ratio=values.count(None) / sampled_rows if sampled_rows else None,
        status=verdict.status,
        sensitive=verdict.sensitive,
        categories=verdict.categories,
        masked_samples=[mask(value, sample_kind) for value in islice(distinct_values, 3)],
        findings=[_to_finding(item) for item in detection.detections],
        suppressed=[
            Suppression(rule_id=record.rule_id, context=record.context, detector=record.detector)
            for record in detection.suppressed
        ],
    )


def run_scan(
    connector: Connector, request: ScanRequest, progress: Callable[[str], None] | None = None
) -> Scan:
    started_at = datetime.now(UTC)
    source = connector.source()
    table_infos = connector.list_tables(schemas=request.schemas, exclude=request.exclude_tables)
    tables: list[Table] = []
    for index, info in enumerate(table_infos, start=1):
        if progress is not None:
            progress(f"Escaneando {info.schema}.{info.name} ({index}/{len(table_infos)})")
        sample = TableSample(rows=0, values={})
        error = None
        if any(column.sampled for column in info.columns):
            try:
                sample = connector.sample(info, request.sample_size)
            except TableReadError as exc:
                error = str(exc)
        tables.append(Table(
            schema_name=info.schema,
            name=info.name,
            estimated_rows=info.estimated_rows,
            sampled_rows=sample.rows,
            error=error,
            columns=[_scan_column(info.name, column, sample) for column in info.columns],
        ))

    columns = [column for table in tables for column in table.columns]
    return Scan(
        rastro_version=__version__,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        source=source,
        settings=Settings(
            sample_size=request.sample_size,
            schemas=request.schemas,
            excluded_tables=request.exclude_tables,
            layers=["name", "pattern"],
        ),
        summary=Summary(
            tables=len(tables),
            columns=len(columns),
            personal=sum(column.status == Status.PERSONAL for column in columns),
            sensitive=sum(column.sensitive for column in columns),
            ambiguous=sum(column.status == Status.AMBIGUOUS for column in columns),
            failed_tables=sum(table.error is not None for table in tables),
        ),
        tables=tables,
    )

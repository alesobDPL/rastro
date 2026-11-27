from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from rastro.detection.thresholds import CONFIDENCE_THRESHOLD
from rastro.models import Column, Detector, Scan, Status

_LABEL_FIELDS = ["schema", "table", "column", "split", "personal", "sensitive", "category", "note"]
_SPLITS = ("dev", "holdout")
_LAYER_BY_DETECTORS = {
    frozenset({Detector.NAME}): "name_only",
    frozenset({Detector.PATTERN}): "pattern_only",
    frozenset({Detector.NAME, Detector.PATTERN}): "both",
}


@dataclass
class LabelRow:
    schema: str
    table: str
    column: str
    split: str
    personal: bool
    sensitive: bool
    category: str
    note: str


@dataclass
class SplitMetrics:
    split: str
    labeled: int
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float | None
    recall: float | None
    f1: float | None
    sensitive_recall: float | None
    ambiguous: int
    ambiguous_personal: int
    by_layer: dict[str, int]
    suppressions: dict[str, int]
    false_positives: list[str] | None
    false_negatives: list[str] | None


@dataclass
class Metrics:
    splits: dict[str, SplitMetrics]
    unlabeled: list[str]


def _parse_boolean(value: str) -> bool:
    if value not in ("true", "false"):
        raise ValueError("La etiqueta contiene un valor booleano no válido.")
    return value == "true"


def load_labels(path: Path) -> list[LabelRow]:
    labels = []
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames != _LABEL_FIELDS:
                raise ValueError("El encabezado de las etiquetas no es válido.")
            for row in reader:
                if None in row or None in row.values():
                    raise ValueError("Una fila de etiquetas tiene un número de campos incorrecto.")
                if row["split"] not in _SPLITS:
                    raise ValueError("La etiqueta contiene una partición no válida.")
                labels.append(LabelRow(
                    schema=row["schema"],
                    table=row["table"],
                    column=row["column"],
                    split=row["split"],
                    personal=_parse_boolean(row["personal"]),
                    sensitive=_parse_boolean(row["sensitive"]),
                    category=row["category"],
                    note=row["note"],
                ))
    except (csv.Error, UnicodeDecodeError):
        raise ValueError("El archivo de etiquetas debe ser un CSV válido en UTF-8.") from None
    return labels


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _evaluate_split(
    split: str, labels: Sequence[LabelRow], columns: dict[tuple[str, str, str], Column],
) -> SplitMetrics:
    tp = fp = fn = tn = 0
    ambiguous = ambiguous_personal = sensitive_labeled = sensitive_detected = 0
    private = split == "holdout"
    by_layer = dict.fromkeys(_LAYER_BY_DETECTORS.values(), 0)
    suppressions = {"total": 0} if private else {}
    false_positives: list[str] | None = None if private else []
    false_negatives: list[str] | None = None if private else []

    for label in labels:
        key = (label.schema, label.table, label.column)
        column = columns.get(key)
        predicted_personal = column is not None and column.status == Status.PERSONAL
        sensitive_labeled += label.sensitive

        if label.personal and predicted_personal:
            tp += 1
        elif predicted_personal:
            fp += 1
            if false_positives is not None:
                false_positives.append(".".join(key))
        elif label.personal:
            fn += 1
            if false_negatives is not None:
                false_negatives.append(".".join(key))
        else:
            tn += 1

        if column is None:
            continue

        sensitive_detected += label.sensitive and column.sensitive
        if column.status == Status.AMBIGUOUS:
            ambiguous += 1
            ambiguous_personal += label.personal
        if label.personal and predicted_personal:
            detectors = frozenset(
                finding.detector for finding in column.findings
                if finding.confidence >= CONFIDENCE_THRESHOLD
            )
            layer = _LAYER_BY_DETECTORS.get(detectors)
            if layer is not None:
                by_layer[layer] += 1

        if private:
            suppressions["total"] += len(column.suppressed)
        else:
            for suppression in column.suppressed:
                suppression_key = f"{suppression.rule_id}|{suppression.context}"
                suppressions[suppression_key] = suppressions.get(suppression_key, 0) + 1

    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None:
        f1 = _ratio(2 * precision * recall, precision + recall)

    return SplitMetrics(
        split=split,
        labeled=len(labels),
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=precision,
        recall=recall,
        f1=f1,
        sensitive_recall=_ratio(sensitive_detected, sensitive_labeled),
        ambiguous=ambiguous,
        ambiguous_personal=ambiguous_personal,
        by_layer=by_layer,
        suppressions=suppressions,
        false_positives=sorted(false_positives) if false_positives is not None else None,
        false_negatives=sorted(false_negatives) if false_negatives is not None else None,
    )


def _evaluate(scan: Scan, labels: Sequence[LabelRow]) -> tuple[Metrics, int]:
    columns = {
        (table.schema_name, table.name, column.name): column
        for table in scan.tables for column in table.columns
    }
    labels_by_split: dict[str, list[LabelRow]] = {split: [] for split in _SPLITS}
    for label in labels:
        labels_by_split[label.split].append(label)

    labeled_keys = {(label.schema, label.table, label.column) for label in labels}
    unlabeled_keys = columns.keys() - labeled_keys
    dev_tables = {(label.schema, label.table) for label in labels_by_split["dev"]}
    holdout_tables = {(label.schema, label.table) for label in labels_by_split["holdout"]}
    private_tables = holdout_tables - dev_tables
    private_schemas = (
        {schema for schema, _ in holdout_tables} - {schema for schema, _ in dev_tables}
    )
    unlabeled = sorted(
        ".".join((schema, table, column))
        for schema, table, column in unlabeled_keys
        if schema not in private_schemas and (schema, table) not in private_tables
    )

    splits = {
        split: _evaluate_split(split, split_labels, columns)
        for split, split_labels in labels_by_split.items()
    }
    return Metrics(splits, unlabeled), len(unlabeled_keys)


def evaluate(scan: Scan, labels: Sequence[LabelRow]) -> Metrics:
    metrics, _ = _evaluate(scan, labels)
    return metrics


def _format_score(score: float | None) -> str:
    return "n/a" if score is None else f"{score:.3f}"


def _print_summary(metrics: Metrics, unlabeled_count: int) -> None:
    for split in metrics.splits.values():
        print(f"Partición {split.split}")
        print(f"  Columnas etiquetadas {split.labeled}")
        print(f"  Verdaderos positivos {split.tp} | Verdaderos negativos {split.tn}")
        print(f"  Falsos positivos {split.fp} | Falsos negativos {split.fn}")
        print(
            f"  Precisión {_format_score(split.precision)} | "
            f"Exhaustividad {_format_score(split.recall)} | F1 {_format_score(split.f1)}"
        )
        print(f"  Exhaustividad de datos sensibles {_format_score(split.sensitive_recall)}")
        print(
            f"  Columnas ambiguas {split.ambiguous} | "
            f"Ambiguas personales {split.ambiguous_personal}"
        )
        print(
            f"  Solo nombre {split.by_layer['name_only']} | "
            f"Solo patrón {split.by_layer['pattern_only']} | Ambas capas {split.by_layer['both']}"
        )
        print(f"  Anulaciones de contexto {sum(split.suppressions.values())}")
        if split.split == "dev":
            for key, count in sorted(split.suppressions.items()):
                print(f"    {key} = {count}")
            if split.false_positives:
                print("  Detalle de falsos positivos")
                for key in split.false_positives:
                    print(f"    {key}")
            if split.false_negatives:
                print("  Detalle de falsos negativos")
                for key in split.false_negatives:
                    print(f"    {key}")

    if unlabeled_count:
        warning = (
            "Se omitió 1 columna sin etiqueta." if unlabeled_count == 1
            else f"Se omitieron {unlabeled_count} columnas sin etiqueta."
        )
        print(f"Aviso. {warning}", file=sys.stderr)
        for key in metrics.unlabeled:
            print(f"  {key}", file=sys.stderr)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, "Los argumentos no son válidos. Consulte --help.\n")


class _HelpFormatter(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix="Uso: " if prefix is None else prefix)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _ArgumentParser(
        description="Compara un escaneo con las etiquetas y guarda las métricas por partición.",
        add_help=False,
        formatter_class=_HelpFormatter,
    )
    required = parser.add_argument_group("Argumentos posicionales")
    required.add_argument("scan_json", type=Path, help="Archivo JSON del escaneo")
    required.add_argument("labels_csv", type=Path, help="Archivo CSV de etiquetas")
    options = parser.add_argument_group("Opciones")
    options.add_argument("-h", "--help", action="help", help="Muestra esta ayuda y sale")
    options.add_argument(
        "--results-dir", type=Path, default=Path("eval/results"), metavar="CARPETA",
        help="Carpeta de resultados (por defecto, eval/results)",
    )
    args = parser.parse_args(argv)

    try:
        scan = Scan.from_json(args.scan_json.read_text(encoding="utf-8"))
    except OSError:
        print("No se pudo leer el archivo de escaneo.", file=sys.stderr)
        return 1
    except ValueError:
        print("El JSON del escaneo no es válido.", file=sys.stderr)
        return 1

    try:
        labels = load_labels(args.labels_csv)
    except OSError:
        print("No se pudo leer el archivo de etiquetas.", file=sys.stderr)
        return 1
    except ValueError:
        print("El archivo de etiquetas no es válido.", file=sys.stderr)
        return 1

    metrics, unlabeled_count = _evaluate(scan, labels)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    results_path = args.results_dir / f"metrics-{timestamp}.json"
    try:
        args.results_dir.mkdir(parents=True, exist_ok=True)
        results_path.write_text(
            json.dumps(asdict(metrics), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        print("No se pudo guardar el archivo de métricas.", file=sys.stderr)
        return 1

    _print_summary(metrics, unlabeled_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import csv
import json
import re
from collections.abc import Sequence
from pathlib import Path

import pytest

from eval.evaluate import LabelRow, evaluate, load_labels, main
from rastro.detection.thresholds import CONFIDENCE_THRESHOLD
from rastro.models import Column, Detector, Finding, Scan, Status, Suppression, Table

LABEL_HEADER = ("schema", "table", "column", "split", "personal", "sensitive", "category", "note")


def _column(
    name: str,
    status: Status = Status.NOT_PERSONAL,
    *,
    sensitive: bool = False,
    findings: Sequence[Finding] = (),
    suppressed: Sequence[Suppression] = (),
) -> Column:
    return Column(
        name=name,
        data_type="text",
        nullable=True,
        null_ratio=None,
        status=status,
        sensitive=sensitive,
        categories=[],
        masked_samples=[],
        findings=list(findings),
        suppressed=list(suppressed),
    )


def _table(*columns: Column, schema: str = "sandbox", name: str = "records") -> Table:
    return Table(
        schema_name=schema, name=name, estimated_rows=None, sampled_rows=0,
        error=None, columns=list(columns),
    )


def _scan(*tables: Table) -> Scan:
    columns = [column for table in tables for column in table.columns]
    return Scan.model_validate({
        "rastro_version": "0.0.0",
        "started_at": "2026-11-27T00:00:00Z",
        "finished_at": "2026-11-27T00:00:00Z",
        "source": {
            "engine": "postgresql", "host": None, "port": None,
            "database": "sample", "user": "tester",
        },
        "settings": {"sample_size": 0, "schemas": [], "excluded_tables": [], "layers": []},
        "summary": {
            "tables": len(tables),
            "columns": len(columns),
            "personal": sum(column.status == Status.PERSONAL for column in columns),
            "sensitive": sum(column.sensitive for column in columns),
            "ambiguous": sum(column.status == Status.AMBIGUOUS for column in columns),
            "failed_tables": 0,
        },
        "tables": list(tables),
    })


def _label(
    column: str,
    *,
    personal: bool,
    sensitive: bool = False,
    split: str = "dev",
    schema: str = "sandbox",
    table: str = "records",
) -> LabelRow:
    category = "sensitive" if sensitive else "identifier" if personal else ""
    return LabelRow(schema, table, column, split, personal, sensitive, category, "")


def _finding(detector: Detector, confidence: float = CONFIDENCE_THRESHOLD) -> Finding:
    return Finding(
        category="identifier", sensitivity="medium", confidence=confidence,
        detector=detector, rule_id="sample_rule", evidence="***",
    )


def _cli_args(tmp_path: Path, scan: Scan, labels: Sequence[LabelRow]) -> list[str]:
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(scan.to_json(), encoding="utf-8")
    labels_path = tmp_path / "labels.csv"
    with labels_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(LABEL_HEADER)
        for label in labels:
            writer.writerow((
                label.schema, label.table, label.column, label.split,
                str(label.personal).lower(), str(label.sensitive).lower(),
                label.category, label.note,
            ))
    return [str(scan_path), str(labels_path), "--results-dir", str(tmp_path / "results")]


def test_confusion_and_scores():
    scan = _scan(_table(
        _column("detected", Status.PERSONAL),
        _column("uncertain", Status.AMBIGUOUS),
        _column("mistaken", Status.PERSONAL),
        _column("ordinary"),
    ))
    labels = [
        _label("detected", personal=True),
        _label("uncertain", personal=True),
        _label("mistaken", personal=False),
        _label("ordinary", personal=False),
    ]

    dev = evaluate(scan, labels).splits["dev"]

    assert dev.split == "dev"
    assert dev.labeled == 4
    assert (dev.tp, dev.fn, dev.fp, dev.tn) == (1, 1, 1, 1)
    assert dev.precision == dev.recall == dev.f1 == 0.5
    assert dev.false_positives == ["sandbox.records.mistaken"]
    assert dev.false_negatives == ["sandbox.records.uncertain"]


def test_missing_labeled_column_is_fn():
    metrics = evaluate(_scan(), [_label("missing", personal=True, sensitive=True)])

    dev = metrics.splits["dev"]
    assert (dev.labeled, dev.fn, dev.sensitive_recall) == (1, 1, 0.0)
    assert dev.false_negatives == ["sandbox.records.missing"]


def test_unlabeled_column_ignored():
    scan = _scan(_table(
        _column("last", Status.PERSONAL), _column("labeled"), _column("first", Status.PERSONAL),
    ))

    metrics = evaluate(scan, [_label("labeled", personal=False)])

    dev = metrics.splits["dev"]
    assert (dev.labeled, dev.tp, dev.fn, dev.fp, dev.tn) == (1, 0, 0, 0, 1)
    assert metrics.unlabeled == ["sandbox.records.first", "sandbox.records.last"]


def test_sensitive_recall_and_ambiguous():
    scan = _scan(_table(
        _column("sensitive", Status.AMBIGUOUS, sensitive=True),
        _column("missed", Status.PERSONAL),
        _column("ordinary", Status.AMBIGUOUS, sensitive=True),
    ))
    labels = [
        _label("sensitive", personal=True, sensitive=True),
        _label("missed", personal=True, sensitive=True),
        _label("ordinary", personal=False),
    ]

    dev = evaluate(scan, labels).splits["dev"]

    assert dev.sensitive_recall == 0.5
    assert (dev.ambiguous, dev.ambiguous_personal) == (2, 1)


def test_by_layer():
    name = _finding(Detector.NAME)
    pattern = _finding(Detector.PATTERN)
    below_threshold = _finding(Detector.PATTERN, CONFIDENCE_THRESHOLD / 2)
    scan = _scan(_table(
        _column("by_name", Status.PERSONAL, findings=[name, name, below_threshold]),
        _column("by_pattern", Status.PERSONAL, findings=[pattern]),
        _column("by_both", Status.PERSONAL, findings=[name, pattern]),
        _column("weak", Status.PERSONAL, findings=[below_threshold]),
        _column("mistaken", Status.PERSONAL, findings=[name, pattern]),
    ))
    labels = [
        _label(column.name, personal=column.name != "mistaken")
        for column in scan.tables[0].columns
    ]

    dev = evaluate(scan, labels).splits["dev"]

    assert dev.tp == 4
    assert dev.by_layer == {"name_only": 1, "pattern_only": 1, "both": 1}


def test_suppressions_counted():
    suppression = Suppression(rule_id="sample", context="metadata", detector=Detector.NAME)
    scan = _scan(_table(
        _column("first", suppressed=[suppression]),
        _column("second", suppressed=[suppression]),
        _column("unlabeled", suppressed=[suppression]),
    ))
    labels = [_label("first", personal=False), _label("second", personal=False)]

    assert evaluate(scan, labels).splits["dev"].suppressions == {"sample|metadata": 2}


def test_holdout_hides_errors(tmp_path, capsys):
    suppression = Suppression(
        rule_id="sealed_rule", context="sealed_context", detector=Detector.NAME,
    )
    scan = _scan(
        _table(_column("known"), _column("visible_unlabeled")),
        _table(
            _column("sealed_fp", Status.PERSONAL, suppressed=[suppression]),
            _column("sealed_unlabeled"),
            schema="sealed_schema", name="sealed_table",
        ),
        _table(_column("sealed_mixed_unlabeled"), name="sealed_mixed_table"),
    )
    labels = [
        _label("known", personal=False),
        _label(
            "sealed_fp", personal=False, split="holdout",
            schema="sealed_schema", table="sealed_table",
        ),
        _label(
            "sealed_fn", personal=True, split="holdout",
            schema="sealed_schema", table="sealed_table",
        ),
        _label("sealed_missing", personal=False, split="holdout", table="sealed_mixed_table"),
    ]

    metrics = evaluate(scan, labels)
    holdout = metrics.splits["holdout"]
    assert (holdout.labeled, holdout.fp, holdout.fn, holdout.tn) == (3, 1, 1, 1)
    assert holdout.false_positives is holdout.false_negatives is None
    assert holdout.suppressions == {"total": 1}
    assert metrics.unlabeled == ["sandbox.records.visible_unlabeled"]

    assert main(_cli_args(tmp_path, scan, labels)) == 0

    captured = capsys.readouterr()
    files = list((tmp_path / "results").iterdir())
    assert len(files) == 1
    assert re.fullmatch(r"metrics-\d{8}-\d{6}\.json", files[0].name)
    saved_text = files[0].read_text(encoding="utf-8")
    for output in (captured.out, captured.err, saved_text, repr(metrics)):
        assert "sealed_" not in output
    assert "3 columnas sin etiqueta" in captured.err
    assert "sandbox.records.visible_unlabeled" in captured.err
    saved = json.loads(saved_text)
    assert saved["unlabeled"] == metrics.unlabeled
    assert saved["splits"]["holdout"]["false_positives"] is None
    assert saved["splits"]["holdout"]["false_negatives"] is None
    assert saved["splits"]["holdout"]["suppressions"] == {"total": 1}


def test_division_by_zero(tmp_path, capsys):
    scan = _scan(_table(_column("ordinary")))
    labels = [_label("ordinary", personal=False)]

    metrics = evaluate(scan, labels)

    assert set(metrics.splits) == {"dev", "holdout"}
    assert metrics.splits["holdout"].labeled == 0
    dev = metrics.splits["dev"]
    assert dev.precision is dev.recall is dev.f1 is dev.sensitive_recall is None
    assert main(_cli_args(tmp_path, scan, labels)) == 0
    assert "Precisión n/a" in capsys.readouterr().out


def test_load_labels_preserves_utf8_and_quoted_note(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text(
        ",".join(LABEL_HEADER)
        + '\npublic,términos,año,dev,true,false,identifier,"nota, con coma"\n',
        encoding="utf-8",
    )

    assert load_labels(path) == [
        LabelRow("public", "términos", "año", "dev", True, False, "identifier", "nota, con coma"),
    ]


@pytest.mark.parametrize(
    ("header", "row", "error"),
    [
        (LABEL_HEADER[::-1], "", "encabezado"),
        (LABEL_HEADER, "s,t,c,prueba,true,false,,", "partición"),
        (LABEL_HEADER, "s,t,c,dev,True,false,,", "booleano"),
        (LABEL_HEADER, "s,t,c,dev,true,0,,", "booleano"),
        (LABEL_HEADER, "s,t,c,dev,true,false,", "fila"),
    ],
)
def test_load_labels_rejects_invalid_data(tmp_path, header, row, error):
    path = tmp_path / "labels.csv"
    path.write_text(",".join(header) + "\n" + row, encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        load_labels(path)


@pytest.mark.parametrize(
    ("argument", "content", "message"),
    [
        (0, None, "No se pudo leer el archivo de escaneo."),
        (0, '{"sealed_bad_input":', "El JSON del escaneo no es válido."),
        (0, '{"sealed_bad_input": 1}', "El JSON del escaneo no es válido."),
        (1, None, "No se pudo leer el archivo de etiquetas."),
        (1, "sealed_bad_input", "El archivo de etiquetas no es válido."),
    ],
)
def test_main_reports_input_errors_without_details(tmp_path, capsys, argument, content, message):
    args = _cli_args(tmp_path, _scan(), [])
    path = Path(args[argument])
    if content is None:
        path.unlink()
    else:
        path.write_text(content, encoding="utf-8")

    assert main(args) == 1

    captured = capsys.readouterr()
    assert captured.err == message + "\n"
    assert captured.out == ""
    assert not (tmp_path / "results").exists()


def test_main_invalid_arguments_exit_with_code_two(capsys):
    with pytest.raises(SystemExit) as error:
        main(["scan.json", "labels.csv", "--sealed_bad_argument"])

    assert error.value.code == 2
    assert capsys.readouterr().err == "Los argumentos no son válidos. Consulte --help.\n"

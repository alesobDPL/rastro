from pathlib import Path

from eval.dataset.build import build_dataset, label_rows, write_labels
from rastro.models import Category


def test_deterministic():
    assert build_dataset(1) == build_dataset(1)
    assert build_dataset(1) != build_dataset(2)


def test_schemas_and_splits():
    schemas = {schema.name: schema for schema in build_dataset().schemas}
    assert {name: schema.split for name, schema in schemas.items()} == {
        "veterinaria": "dev",
        "ecommerce": "dev",
        "colegio": "holdout",
    }
    dev_tables = schemas["veterinaria"].tables + schemas["ecommerce"].tables
    assert 35 <= len(dev_tables) <= 45
    assert sum(len(table.columns) for table in dev_tables) >= 250
    assert 8 <= len(schemas["colegio"].tables) <= 12


def test_rows_per_table():
    for schema in build_dataset().schemas:
        for table in schema.tables:
            assert 100 <= len(table.rows) <= 500
            assert all(len(row) == len(table.columns) for row in table.rows)


def test_minimums():
    rows = [row for row in label_rows(build_dataset()) if row["split"] == "dev"]
    assert sum(row["personal"] == "true" for row in rows) / len(rows) >= 0.30
    assert sum(row["sensitive"] == "true" for row in rows) >= 15
    for prefix in ("trampa_fp", "trampa_fn", "texto_libre"):
        assert sum(row["note"].startswith(prefix) for row in rows) >= 10


def test_label_consistency():
    categories = {category.value for category in Category}
    for row in label_rows(build_dataset()):
        assert row["personal"] in {"true", "false"}
        assert row["sensitive"] in {"true", "false"}
        if row["sensitive"] == "true":
            assert row["personal"] == "true"
        if row["personal"] == "false":
            assert row["category"] == ""
        else:
            assert row["category"] in categories
        if row["category"] == Category.MINORS:
            assert row["sensitive"] == "true"


def test_forbidden_example_names():
    names = {row["column"] for row in label_rows(build_dataset())}
    assert names.isdisjoint(
        {
            "campo_3",
            "ref_cliente",
            "email_template_id",
            "rut_empresa_emisora",
            "telefono_soporte_tienda",
            "obs",
            "diagnostico_mascota",
        }
    )


def test_labels_file_up_to_date(tmp_path):
    generated = tmp_path / "labels.csv"
    write_labels(build_dataset(), generated)
    committed = Path(__file__).resolve().parents[2] / "eval" / "dataset" / "labels.csv"
    assert committed.read_text(encoding="utf-8") == generated.read_text(encoding="utf-8")

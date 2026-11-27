import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from rastro.models import (
    Category,
    Column,
    Detector,
    Finding,
    Scan,
    Sensitivity,
    Settings,
    Source,
    Status,
    Summary,
    Suppression,
    Table,
)


@pytest.fixture
def scan() -> Scan:
    finding = Finding(
        category=Category.CONTACT,
        sensitivity=Sensitivity.LOW,
        confidence=0.9,
        detector=Detector.NAME,
        rule_id="name.email",
        evidence="email",
    )
    column = Column(
        name="email",
        data_type="text",
        nullable=True,
        null_ratio=0.0,
        status=Status.PERSONAL,
        sensitive=False,
        categories=[Category.CONTACT],
        masked_samples=["a***@e***.example"],
        findings=[finding],
        suppressed=[Suppression(rule_id="name.contact", context="id", detector=Detector.NAME)],
    )
    return Scan(
        rastro_version="0.1.0",
        started_at=datetime(2026, 11, 27, 9, 0, tzinfo=timezone(timedelta(hours=-3))),
        finished_at=datetime(2026, 11, 27, 12, 1),
        source=Source(engine="postgresql", host=None, port=None, database="rastro", user="rastro"),
        settings=Settings(sample_size=10, schemas=["public"], excluded_tables=[], layers=["name"]),
        summary=Summary(tables=1, columns=1, personal=1, sensitive=0, ambiguous=0, failed_tables=0),
        tables=[
            Table(
                schema_name="public",
                name="contacts",
                estimated_rows=10,
                sampled_rows=10,
                error=None,
                columns=[column],
            )
        ],
    )


def test_scan_roundtrip(scan: Scan) -> None:
    text = scan.to_json()
    payload = json.loads(text)
    assert payload["started_at"] == "2026-11-27T12:00:00Z"
    assert payload["finished_at"] == "2026-11-27T12:01:00Z"
    assert Scan.from_json(text) == scan


def test_table_serializes_schema_alias(scan: Scan) -> None:
    table = json.loads(scan.to_json())["tables"][0]
    assert table["schema"] == "public"
    assert "schema_name" not in table


def test_schema_version_is_1(scan: Scan) -> None:
    payload = json.loads(scan.to_json())
    assert payload["schema_version"] == "1"

    payload["schema_version"] = "2"
    with pytest.raises(ValidationError, match="schema_version"):
        Scan.from_json(json.dumps(payload))


def test_extra_field_rejected(scan: Scan) -> None:
    column = scan.tables[0].columns[0].model_dump()
    with pytest.raises(ValidationError, match="unexpected_field"):
        Column.model_validate({**column, "unexpected_field": True})


def test_masked_samples_max_3(scan: Scan) -> None:
    column = scan.tables[0].columns[0].model_dump()
    with pytest.raises(ValidationError, match="masked_samples"):
        Column.model_validate({**column, "masked_samples": ["a*", "b*", "c*", "d*"]})


def test_confidence_range(scan: Scan) -> None:
    finding = scan.tables[0].columns[0].findings[0].model_dump()
    for confidence in (-0.1, 1.2):
        with pytest.raises(ValidationError, match="confidence"):
            Finding.model_validate({**finding, "confidence": confidence})


def test_password_not_a_field() -> None:
    assert "password" not in Source.model_fields


def test_json_schema_file_up_to_date() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "scan-v1.schema.json"
    assert json.loads(schema_path.read_text(encoding="utf-8")) == Scan.model_json_schema(
        by_alias=True
    )

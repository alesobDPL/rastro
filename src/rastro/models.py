from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Category(StrEnum):
    IDENTIFIER = "identifier"
    CONTACT = "contact"
    LOCATION = "location"
    FINANCIAL = "financial"
    SENSITIVE = "sensitive"
    MINORS = "minors"


class Sensitivity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Status(StrEnum):
    PERSONAL = "personal"
    AMBIGUOUS = "ambiguous"
    NOT_PERSONAL = "not_personal"


class Detector(StrEnum):
    NAME = "name"
    PATTERN = "pattern"


class SensitiveSubcategory(StrEnum):
    HEALTH = "health"
    BIOMETRIC = "biometric"
    ETHNIC_ORIGIN = "ethnic_origin"
    BELIEFS = "beliefs"
    SEXUAL_ORIENTATION = "sexual_orientation"
    POLITICAL_AFFILIATION = "political_affiliation"
    UNION_AFFILIATION = "union_affiliation"


class ValueKind(StrEnum):
    RUT = "rut"
    EMAIL = "email"
    PHONE = "phone"
    CARD = "card"
    PLATE = "plate"
    GENERIC = "generic"


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Finding(_ContractModel):
    category: Category
    subcategory: SensitiveSubcategory | None = None
    sensitivity: Sensitivity
    confidence: float = Field(ge=0, le=1)
    detector: Detector
    rule_id: str
    evidence: str


class Suppression(_ContractModel):
    rule_id: str
    context: str
    detector: Detector


class Column(_ContractModel):
    name: str
    data_type: str
    nullable: bool
    null_ratio: float | None
    status: Status
    sensitive: bool
    categories: list[Category]
    masked_samples: list[str] = Field(max_length=3)
    findings: list[Finding]
    suppressed: list[Suppression] = []


class Table(_ContractModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_name: str = Field(alias="schema")
    name: str
    estimated_rows: int | None
    sampled_rows: int
    error: str | None
    columns: list[Column]


class Source(_ContractModel):
    engine: Literal["postgresql"] = Field(json_schema_extra={"type": "string"})
    host: str | None
    port: int | None
    database: str
    user: str


class Settings(_ContractModel):
    sample_size: int
    schemas: list[str]
    excluded_tables: list[str]
    layers: list[Literal["name", "pattern"]]


class Summary(_ContractModel):
    tables: int
    columns: int
    personal: int
    sensitive: int
    ambiguous: int
    failed_tables: int


class Scan(_ContractModel):
    schema_version: Literal["1"] = Field(default="1", json_schema_extra={"type": "string"})
    rastro_version: str
    started_at: datetime
    finished_at: datetime
    source: Source
    settings: Settings
    summary: Summary
    tables: list[Table]

    @field_validator("started_at", "finished_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, indent=2)

    @classmethod
    def from_json(cls, text: str) -> Scan:
        return cls.model_validate_json(text)


def export_json_schema(path: Path) -> None:
    schema = Scan.model_json_schema(by_alias=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    export_json_schema(Path("schemas/scan-v1.schema.json"))

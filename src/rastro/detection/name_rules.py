from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from importlib.resources import files

import yaml

from rastro.detection.normalize import normalize_name
from rastro.models import Category, SensitiveSubcategory, Sensitivity


@dataclass(frozen=True)
class _NameRule:
    rule_id: str
    category: Category
    subcategory: SensitiveSubcategory | None
    confidence: float
    unless: frozenset[str]


def _load_yaml(filename: str) -> dict:
    path = files("rastro.detection").joinpath("rules", filename)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _normalized_tokens(values: Sequence[str]) -> frozenset[str]:
    return frozenset(token for value in values for token in normalize_name(value))


@cache
def _rules_by_first_token() -> dict[str, list[tuple[tuple[str, ...], _NameRule]]]:
    rules: dict[str, list[tuple[tuple[str, ...], _NameRule]]] = {}
    for entry in _load_yaml("names.yml")["rules"]:
        rule = _NameRule(
            rule_id=entry["id"],
            category=Category(entry["category"]),
            subcategory=(
                SensitiveSubcategory(entry["subcategory"]) if "subcategory" in entry else None
            ),
            confidence=entry["confidence"],
            unless=_normalized_tokens(entry.get("unless", [])),
        )
        for phrase in entry["tokens"]:
            tokens = tuple(normalize_name(phrase))
            rules.setdefault(tokens[0], []).append((tokens, rule))
    for candidates in rules.values():
        candidates.sort(key=lambda candidate: len(candidate[0]), reverse=True)
    return rules


@cache
def _context_tokens() -> dict[str, frozenset[str]]:
    return {kind: _normalized_tokens(values) for kind, values in _load_yaml("context.yml").items()}


@cache
def _sensitivities() -> dict[Category, Sensitivity]:
    categories = _load_yaml("categories.yml")
    return {Category(category): Sensitivity(value) for category, value in categories.items()}


def category_sensitivity(category: Category) -> Sensitivity:
    return _sensitivities()[category]


def matching_name_rules(tokens: Sequence[str]) -> Iterator[tuple[_NameRule, str]]:
    tokens = tuple(tokens)
    rules = _rules_by_first_token()
    matches: dict[_NameRule, tuple[str, ...]] = {}
    start = 0
    while start < len(tokens):
        # A compound phrase takes precedence over its individual tokens.
        for phrase, rule in rules.get(tokens[start], ()):
            end = start + len(phrase)
            if tokens[start:end] == phrase:
                if len(phrase) > len(matches.get(rule, ())):
                    matches[rule] = phrase
                start = end
                break
        else:
            start += 1
    for rule, phrase in matches.items():
        yield rule, " ".join(phrase)


def suppression_context(
    table_tokens: Sequence[str],
    column_tokens: Sequence[str],
    *,
    has_personal_name: bool,
) -> str | None:
    context = _context_tokens()
    organizations = context["organization"]
    organization = next(
        (token for token in (*column_tokens, *table_tokens) if token in organizations), None
    )
    if organization is not None:
        return organization
    if has_personal_name:
        metadata = next((token for token in column_tokens if token in context["metadata"]), None)
        if metadata is not None:
            return metadata
    if column_tokens and column_tokens[-1] in context["suffixes"]:
        return f"suffix:{column_tokens[-1]}"
    return None


def has_free_text_token(tokens: Sequence[str]) -> bool:
    return not _context_tokens()["free_text"].isdisjoint(tokens)

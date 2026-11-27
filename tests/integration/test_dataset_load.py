from collections import Counter

import psycopg
import pytest

from eval.dataset.build import build_dataset
from eval.dataset.load import load_dataset


@pytest.mark.integration
def test_load_from_scratch(pg_url):
    load_dataset(pg_url)
    load_dataset(pg_url)

    expected = {schema.name: len(schema.tables) for schema in build_dataset().schemas}
    with psycopg.connect(pg_url) as conn:
        tables = conn.execute(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_schema = ANY(%s) AND table_type = 'BASE TABLE'",
            (list(expected),),
        )
        assert Counter(schema for (schema,) in tables) == expected

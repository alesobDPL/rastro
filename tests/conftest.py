import os

import psycopg
import pytest


@pytest.fixture(scope="session")
def pg_url() -> str:
    url = os.environ.get("RASTRO_TEST_DB_URL")
    if not url:
        pytest.skip("RASTRO_TEST_DB_URL no está definida")

    try:
        with psycopg.connect(url, connect_timeout=3):
            pass
    except psycopg.Error:
        pytest.skip("La base de datos PostgreSQL de pruebas no está disponible")

    return url

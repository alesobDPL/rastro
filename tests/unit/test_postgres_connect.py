import socket
from threading import Thread
from unittest.mock import Mock

import psycopg
import pytest

from rastro.connectors import postgres
from rastro.connectors.types import ConnectionFailed


@pytest.mark.parametrize(("query", "env_timeout", "expected"), [
    ("", None, 10),
    ("", "", 10),
    ("?connect_timeout=3", None, "3"),
    ("", "4", None),
])
def test_connect_parameters(monkeypatch, query, env_timeout, expected):
    if env_timeout is None:
        monkeypatch.delenv("PGCONNECT_TIMEOUT", raising=False)
    else:
        monkeypatch.setenv("PGCONNECT_TIMEOUT", env_timeout)
    connect = Mock(side_effect=psycopg.OperationalError("x"))
    monkeypatch.setattr(psycopg, "connect", connect)
    connector = postgres.PostgresConnector(f"postgresql://u:p@localhost/db{query}")
    try:
        with pytest.raises(ConnectionFailed):
            connector.list_tables()
    finally:
        connector.close()

    connect.assert_called_once()
    kwargs = connect.call_args.kwargs
    if expected is None:
        assert "connect_timeout" not in kwargs
    else:
        assert kwargs["connect_timeout"] == expected
    assert "default_transaction_read_only=on" in kwargs["options"]
    assert "statement_timeout=30000" in kwargs["options"]


def test_connect_timeout_with_unresponsive_server(monkeypatch):
    monkeypatch.delenv("PGCONNECT_TIMEOUT", raising=False)
    monkeypatch.setattr(postgres, "CONNECT_TIMEOUT_SECONDS", 2, raising=False)
    server = socket.socket()
    try:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        connector = postgres.PostgresConnector(f"postgresql://u:p@127.0.0.1:{port}/db")
        failures = []

        def list_tables():
            try:
                connector.list_tables()
            except ConnectionFailed as exc:
                failures.append(exc)
            finally:
                connector.close()

        thread = Thread(target=list_tables, daemon=True)
        thread.start()
        thread.join(timeout=15)
        assert not thread.is_alive()
        assert len(failures) == 1
    finally:
        server.close()

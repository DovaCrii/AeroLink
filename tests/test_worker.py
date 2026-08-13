import hashlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aerolink.config import Settings
from aerolink.db import Base
from aerolink.models import RawMessage, Workspace
from aerolink.worker import (
    WorkerConfigurationError,
    _get_or_create_default_workspace,
    _require_relay_settings,
    build_client,
    persist_raw_message,
)


@pytest.fixture
def sqlite_session_factory():
    """An isolated, in-memory stand-in for the real Postgres session --
    `db.py` builds its engine from settings at import time, so tests must
    not touch it."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _relay_settings(**overrides) -> Settings:
    defaults = {
        "mqtt_public_host": "relay.example.test",
        "mqtt_worker_username": "aerolink-worker",
        "mqtt_worker_password": "secret",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_require_relay_settings_rejects_a_worker_with_nothing_to_connect_to():
    with pytest.raises(WorkerConfigurationError):
        _require_relay_settings(Settings())


def test_require_relay_settings_accepts_a_fully_configured_relay():
    _require_relay_settings(_relay_settings())  # must not raise


def test_persist_raw_message_creates_the_default_workspace_once(
    sqlite_session_factory,
):
    persist_raw_message(
        "thing/product/1581F/osd", b'{"lat": 1}', session_factory=sqlite_session_factory
    )
    persist_raw_message(
        "thing/product/1581F/status",
        b'{"lat": 2}',
        session_factory=sqlite_session_factory,
    )

    with sqlite_session_factory() as session:
        assert session.query(Workspace).count() == 1
        assert session.query(RawMessage).count() == 2


def test_persist_raw_message_keeps_the_original_bytes_hash(sqlite_session_factory):
    payload = b'{"battery": 87}'

    message = persist_raw_message(
        "thing/product/1581F/osd", payload, session_factory=sqlite_session_factory
    )

    assert message.payload_sha256 == hashlib.sha256(payload).hexdigest()
    assert message.payload_json == {"battery": 87}


def test_persist_raw_message_never_drops_a_non_json_payload(sqlite_session_factory):
    """A message this cannot parse is still evidence -- AL-306's whole point
    is that "we don't understand this yet" is not the same as "discard it"."""
    payload = b"\xff\xfe\x00binary-garbage"

    message = persist_raw_message(
        "thing/product/1581F/unknown",
        payload,
        session_factory=sqlite_session_factory,
    )

    assert message.payload_json["raw_base64"]
    assert message.payload_sha256 == hashlib.sha256(payload).hexdigest()


def test_get_or_create_default_workspace_is_idempotent(sqlite_session_factory):
    with sqlite_session_factory() as session:
        first = _get_or_create_default_workspace(session)
        second = _get_or_create_default_workspace(session)

        assert first.id == second.id


def test_build_client_wires_callbacks_without_connecting(sqlite_session_factory):
    client = build_client(_relay_settings(), session_factory=sqlite_session_factory)

    assert callable(client.on_connect)
    assert callable(client.on_disconnect)
    assert callable(client.on_message)

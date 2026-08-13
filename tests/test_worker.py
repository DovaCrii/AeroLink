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


class _FakeMessage:
    """The attributes `on_message` reads, including the mid it must acknowledge."""

    def __init__(
        self,
        topic: str = "thing/product/1581F/osd",
        payload: bytes = b'{"lat": 1}',
        qos: int = 1,
        mid: int = 7,
    ) -> None:
        self.topic = topic
        self.payload = payload
        self.qos = qos
        self.mid = mid


class _RecordingClient:
    """Stands in for the client paho passes to the callback, to see whether the
    message was acknowledged."""

    def __init__(self) -> None:
        self.acked: list[tuple[int, int]] = []

    def ack(self, mid: int, qos: int) -> None:
        self.acked.append((mid, qos))


def test_build_client_keeps_the_session_and_the_ack_under_our_control(
    sqlite_session_factory,
):
    """The two settings that make the QoS 1 subscription mean something.

    Asserted through paho's private attributes because it exposes no getter for
    either one, and the alternative is a contract that stays invisible until a
    restart loses messages in production.
    """
    client = build_client(_relay_settings(), session_factory=sqlite_session_factory)

    assert client._clean_session is False, "the relay must queue while we are down"
    assert client._manual_ack is True, "paho must not acknowledge before we store"


def test_on_message_acknowledges_only_after_the_message_is_stored(
    sqlite_session_factory,
):
    client = build_client(_relay_settings(), session_factory=sqlite_session_factory)
    recorder = _RecordingClient()
    message = _FakeMessage()

    client.on_message(recorder, None, message)

    with sqlite_session_factory() as session:
        assert session.query(RawMessage).count() == 1
    assert recorder.acked == [(message.mid, message.qos)]


def test_on_message_does_not_acknowledge_a_message_it_could_not_store():
    """A database outage must delay ingestion, not consume the message.

    Without the acknowledgement the relay still owes us this message and
    redelivers it when the session resumes; acknowledging it here would be the
    one way to lose it for good.
    """

    def unreachable_database():
        raise RuntimeError("database is down")

    client = build_client(_relay_settings(), session_factory=unreachable_database)
    recorder = _RecordingClient()

    client.on_message(recorder, None, _FakeMessage())  # must not raise

    assert recorder.acked == []

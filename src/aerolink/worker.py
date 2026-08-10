"""MQTT worker: a *client* of the external relay broker, not a server.

AL-003 confirmed 2026-08-10 that p340 has no inbound path from the public
internet (neither 443 nor 8883 answer from outside its Tailscale network).
DJI Pilot 2 therefore cannot connect to a broker hosted on p340 -- so the
broker lives on an external relay with a real public IP, and this worker
reaches it the one way that already works from p340: an outbound
connection. It never accepts inbound traffic itself.

Scope on purpose: this only proves the outbound architecture and persists
the untouched original message (`RawMessage`, hash included). Parsing DJI's
payload shape into `TelemetrySample`/`FlightSession` is AL-302, after AL-204
has captured real fixtures -- guessing the wire format here would be worse
than not parsing it at all.
"""

import base64
import hashlib
import json
import logging
import ssl
from collections.abc import Callable
from datetime import UTC, datetime

import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session

from aerolink.config import Settings, get_settings
from aerolink.db import SessionLocal
from aerolink.models import RawMessage, Workspace

SessionFactory = Callable[[], Session]

logger = logging.getLogger("aerolink.worker")

DEFAULT_WORKSPACE_SLUG = "default"


class WorkerConfigurationError(RuntimeError):
    """Raised when the settings needed to reach the relay are incomplete."""


def _require_relay_settings(settings: Settings) -> None:
    missing = [
        name
        for name, value in (
            ("MQTT_PUBLIC_HOST", settings.mqtt_public_host),
            ("MQTT_WORKER_USERNAME", settings.mqtt_worker_username),
            ("MQTT_WORKER_PASSWORD", settings.mqtt_worker_password),
        )
        if not value
    ]
    if missing:
        raise WorkerConfigurationError(
            f"Missing relay settings: {', '.join(missing)}. The worker connects "
            "outbound to an external broker (AL-R1) -- it has no default to "
            "fall back to."
        )


def _decode_payload(payload: bytes) -> dict:
    """Best-effort JSON decode; never drop a message just because it isn't JSON."""
    try:
        return json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"raw_base64": base64.b64encode(payload).decode("ascii")}


def _get_or_create_default_workspace(session: Session) -> Workspace:
    """A single workspace until AL-202's bootstrap creates real ones.

    Not a design decision about multi-tenancy -- just the smallest thing
    that lets RawMessage.workspace_id (non-nullable) be satisfied before
    the actual bootstrap flow exists.
    """
    workspace = (
        session.query(Workspace).filter_by(slug=DEFAULT_WORKSPACE_SLUG).one_or_none()
    )
    if workspace is None:
        workspace = Workspace(slug=DEFAULT_WORKSPACE_SLUG, name="Default")
        session.add(workspace)
        session.commit()
    return workspace


def persist_raw_message(
    topic: str,
    payload: bytes,
    *,
    qos: int = 0,
    session_factory: SessionFactory = SessionLocal,
) -> RawMessage:
    """Store the untouched message with its hash. Never raises on payload
    content -- a message this ingests is never lost to a parsing error.

    `session_factory` is injectable so tests can point it at an isolated
    database instead of the real one `db.py` builds from settings at import
    time.
    """
    with session_factory() as session:
        workspace = _get_or_create_default_workspace(session)
        message = RawMessage(
            workspace_id=workspace.id,
            topic=topic,
            received_at=datetime.now(UTC),
            qos=qos,
            payload_json=_decode_payload(payload),
            payload_sha256=hashlib.sha256(payload).hexdigest(),
        )
        session.add(message)
        session.commit()
        logger.info(
            "raw_message_persisted",
            extra={
                "topic": topic,
                "raw_message_id": str(message.id),
                "workspace_id": str(workspace.id),
            },
        )
        return message


def build_client(
    settings: Settings, *, session_factory: SessionFactory = SessionLocal
) -> mqtt.Client:
    """An MQTT client configured to *dial out* to the relay -- TLS via the
    system CA store (the relay carries a real public certificate; this is
    not the self-signed/local-file setup AL-104 needed when the broker was
    still assumed to run on p340)."""
    client = mqtt.Client(
        client_id=settings.mqtt_worker_client_id,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.username_pw_set(settings.mqtt_worker_username, settings.mqtt_worker_password)
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.reconnect_delay_set(min_delay=1, max_delay=60)

    def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            logger.info("relay_connected", extra={"topic": settings.mqtt_worker_topic})
            client.subscribe(settings.mqtt_worker_topic, qos=1)
        else:
            logger.error("relay_connect_failed", extra={"topic": str(reason_code)})

    def on_disconnect(
        client: mqtt.Client, userdata, flags, reason_code, properties=None
    ):
        logger.warning("relay_disconnected", extra={"topic": str(reason_code)})

    def on_message(client: mqtt.Client, userdata, message: mqtt.MQTTMessage):
        persist_raw_message(
            message.topic,
            message.payload,
            qos=message.qos,
            session_factory=session_factory,
        )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    return client


def run() -> None:
    settings = get_settings()
    _require_relay_settings(settings)
    client = build_client(settings)
    logger.info(
        "worker_starting",
        extra={"topic": f"{settings.mqtt_public_host}:{settings.mqtt_tls_port}"},
    )
    client.connect(settings.mqtt_public_host, settings.mqtt_tls_port)
    client.loop_forever()


if __name__ == "__main__":
    run()

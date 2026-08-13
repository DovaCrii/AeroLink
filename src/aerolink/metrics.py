"""Ingestion signals that outlive the process that produced them (AL-106).

The worker's own counters live in `worker.py` and reset when it restarts, which
is exactly when an operator most wants to know what happened. These gauges are
read from the database instead, so they survive a restart, a redeploy and a
crash, and they answer the two questions that matter before the first real
flight:

- **is anything arriving?** `aerolink_raw_message_last_received_timestamp_seconds`
  is `0` when nothing has ever arrived; otherwise an alert is
  `time() - metric > threshold`, which is a stalled ingestion — the failure mode
  the worker's durability design turns a loss into (see `worker.py`).
- **is anything stuck?** `aerolink_ingestion_exceptions_open` is the bandeja of
  AL-306 seen from the outside, before it has a UI.

`refresh_ingestion_metrics` never raises: /metrics staying up while the database
is down is the whole point of `aerolink_ingestion_metrics_available`. A scrape
that fails tells an operator nothing; a scrape that says `available 0` tells them
where to look.
"""

from __future__ import annotations

import logging

from prometheus_client import Gauge
from sqlalchemy import func

from aerolink.db import SessionLocal
from aerolink.models import IngestionException, RawMessage
from aerolink.timeutils import as_utc

logger = logging.getLogger("aerolink.metrics")

RAW_MESSAGES_STORED = Gauge(
    "aerolink_raw_messages_stored",
    "Original DJI messages persisted with their hash.",
)
LAST_RAW_MESSAGE_TIMESTAMP = Gauge(
    "aerolink_raw_message_last_received_timestamp_seconds",
    "Unix time of the most recently stored message; 0 when none has arrived.",
)
OPEN_INGESTION_EXCEPTIONS = Gauge(
    "aerolink_ingestion_exceptions_open",
    "Ingestion exceptions still open (AL-306).",
)
INGESTION_METRICS_AVAILABLE = Gauge(
    "aerolink_ingestion_metrics_available",
    "1 when the last scrape could read the database, 0 when it could not.",
)


def refresh_ingestion_metrics(session_factory=SessionLocal) -> bool:
    """Read the ingestion gauges from the database. Never raises."""
    try:
        with session_factory() as session:
            stored = session.query(func.count(RawMessage.id)).scalar() or 0
            last_received = session.query(func.max(RawMessage.received_at)).scalar()
            open_exceptions = (
                session.query(func.count(IngestionException.id))
                .filter(IngestionException.status == "open")
                .scalar()
                or 0
            )
    except Exception:
        # Deliberately broad: a metrics scrape must not be the thing that
        # turns a database problem into an unreachable endpoint.
        INGESTION_METRICS_AVAILABLE.set(0)
        logger.warning("ingestion_metrics_unavailable", exc_info=True)
        return False

    RAW_MESSAGES_STORED.set(stored)
    OPEN_INGESTION_EXCEPTIONS.set(open_exceptions)
    LAST_RAW_MESSAGE_TIMESTAMP.set(_as_unix_seconds(last_received))
    INGESTION_METRICS_AVAILABLE.set(1)
    return True


def _as_unix_seconds(value) -> float:
    """0 for "never"; `as_utc` for everything else.

    Without the coercion a naive timestamp would be read as local time and drift
    the gauge by the machine's offset. See `timeutils.as_utc` for why the driver
    decides whether it arrives naive.
    """
    if value is None:
        return 0.0
    return as_utc(value).timestamp()

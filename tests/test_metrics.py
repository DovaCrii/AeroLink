"""AL-106: the ingestion gauges, including what they do when the database is gone."""

from datetime import UTC, datetime, timedelta

from prometheus_client import REGISTRY

from aerolink.metrics import refresh_ingestion_metrics
from aerolink.models import IngestionException, RawMessage, Workspace


def _sample(name: str) -> float | None:
    return REGISTRY.get_sample_value(name)


def test_gauges_report_what_has_been_ingested(db_session):
    workspace = Workspace(slug="metrics", name="Metrics")
    db_session.add(workspace)
    db_session.commit()
    received_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.add(
        RawMessage(
            workspace_id=workspace.id,
            topic="thing/product/1581F/osd",
            received_at=received_at,
            qos=1,
            payload_json={"lat": 1},
            payload_sha256="0" * 64,
        )
    )
    db_session.add(
        IngestionException(
            workspace_id=workspace.id,
            kind="relay_session_lost",
            status="open",
            message="the relay did not have our session",
        )
    )
    db_session.add(
        IngestionException(
            workspace_id=workspace.id,
            kind="relay_session_lost",
            status="resolved",
            message="already handled",
        )
    )
    db_session.commit()

    assert refresh_ingestion_metrics(lambda: db_session) is True

    assert _sample("aerolink_raw_messages_stored") == 1
    # Only the open one counts: the gauge is a bandeja to attend, not a history.
    assert _sample("aerolink_ingestion_exceptions_open") == 1
    assert _sample("aerolink_ingestion_metrics_available") == 1
    assert (
        _sample("aerolink_raw_message_last_received_timestamp_seconds")
        == received_at.timestamp()
    )


def test_last_message_timestamp_is_zero_when_nothing_has_arrived(db_session):
    assert refresh_ingestion_metrics(lambda: db_session) is True

    assert _sample("aerolink_raw_messages_stored") == 0
    # 0 rather than "now" or a missing series: an alert on
    # `time() - metric > threshold` must fire for a gateway that never received
    # anything, not stay silent because the metric looks fresh.
    assert _sample("aerolink_raw_message_last_received_timestamp_seconds") == 0


def test_a_database_outage_lowers_availability_instead_of_failing_the_scrape():
    def unreachable_database():
        raise RuntimeError("connection refused")

    assert refresh_ingestion_metrics(unreachable_database) is False  # must not raise

    assert _sample("aerolink_ingestion_metrics_available") == 0


def test_metrics_endpoint_publishes_the_ingestion_series(client):
    """The endpoint refreshes the gauges against the request's session, so the
    `client` fixture's override is what it reads -- not the real database."""
    response = client.get("/metrics")

    assert response.status_code == 200
    for series in (
        "aerolink_raw_messages_stored",
        "aerolink_raw_message_last_received_timestamp_seconds",
        "aerolink_ingestion_exceptions_open",
        "aerolink_ingestion_metrics_available",
    ):
        assert series in response.text
    assert "aerolink_ingestion_metrics_available 1.0" in response.text

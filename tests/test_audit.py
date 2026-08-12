"""AL-107 / ADR-0003: the audit trail for the integration read.

`AuditEvent` had existed since the initial migration with nothing writing to it.
These pin the properties that make it worth having.
"""

from sqlalchemy import select

from aerolink.models import AuditEvent

URL = "/api/v1/devices/"
BATTERY = {"kind": "battery"}


def test_a_successful_read_is_recorded_once(
    client, auth_headers, make_device, db_session, workspace
):
    """One row per request, never one per device: the event is the disclosure,
    not each item in it."""
    make_device(serial="TB65-AAA")
    make_device(serial="TB65-BBB")

    response = client.get(URL, params=BATTERY, headers=auth_headers)

    events = db_session.scalars(select(AuditEvent)).all()
    assert len(events) == 1
    event = events[0]
    assert event.action == "inventory.read"
    assert event.resource_type == "device"
    assert event.resource_id is None
    assert event.workspace_id == workspace.id
    assert event.actor_subject == "svc:aerocontrol"
    assert event.metadata_json["count"] == response.json()["count"] == 2
    assert event.metadata_json["kind"] == "battery"


def test_the_request_id_ties_the_row_to_the_access_log(
    client, auth_headers, make_device, db_session
):
    """Without it the audit row and the JSON log line cannot be correlated."""
    make_device(serial="TB65-AAA")

    client.get(URL, params=BATTERY, headers={**auth_headers, "X-Request-ID": "abc-123"})

    event = db_session.scalars(select(AuditEvent)).one()
    assert event.metadata_json["request_id"] == "abc-123"


def test_a_rejected_call_writes_no_audit_row(client, auth_headers, db_session):
    """Auditing anonymous failures would hand an unauthenticated caller an
    unbounded write into the audit table. That signal belongs in the log, where
    rotation bounds it."""
    client.get(URL, params=BATTERY, headers={"Authorization": "Token wrong"})

    assert db_session.scalars(select(AuditEvent)).all() == []


def test_a_forbidden_kind_writes_no_audit_row(
    client, auth_headers, workspace, db_session
):
    """Nothing was disclosed, so there is nothing to record."""
    client.get(URL, params={"kind": "aircraft"}, headers=auth_headers)

    assert db_session.scalars(select(AuditEvent)).all() == []


def test_a_collision_is_recorded_for_later(
    client, auth_headers, make_device, db_session
):
    """AL-306's exception tray in embryo: two serials that normalize the same
    are dropped to one, and the fact is kept rather than lost."""
    make_device(serial="TB65AAA")
    make_device(serial="tb65aaa")

    client.get(URL, params=BATTERY, headers=auth_headers)

    event = db_session.scalars(select(AuditEvent)).one()
    assert event.metadata_json["collisions"] == ["TB65AAA"]

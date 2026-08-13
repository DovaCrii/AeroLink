"""AL-203: la topología observada, y lo que pasa cuando el serial no calza."""

from datetime import UTC, datetime, timedelta

import pytest

from aerolink.models import DeviceKind, DeviceTopology
from aerolink.topology import TopologyError, record_topology, unresolved_topologies

GATEWAY = "RC1ABC0000000001"
AIRCRAFT = "1581F5FHD24A00000001"


def test_serials_are_normalized_before_anything_else(db_session, workspace):
    """El espacio espurio a mitad del serial es real: dos de las 16 aeronaves del
    padrón lo traen. Sin normalizar, la misma combinación se guardaría dos veces."""
    record_topology(
        db_session,
        workspace_id=workspace.id,
        gateway_serial=f"  {GATEWAY.lower()} ",
        aircraft_serial=f"{AIRCRAFT[:8]} {AIRCRAFT[8:]}",
    )
    db_session.commit()

    stored = db_session.query(DeviceTopology).one()
    assert stored.gateway_serial == GATEWAY
    assert stored.aircraft_serial == AIRCRAFT


def test_the_same_combination_refreshes_instead_of_duplicating(db_session, workspace):
    first_seen = datetime.now(UTC) - timedelta(hours=2)
    first = record_topology(
        db_session,
        workspace_id=workspace.id,
        gateway_serial=GATEWAY,
        aircraft_serial=AIRCRAFT,
        observed_at=first_seen,
    )
    db_session.commit()

    later = first_seen + timedelta(hours=1)
    second = record_topology(
        db_session,
        workspace_id=workspace.id,
        gateway_serial=GATEWAY,
        aircraft_serial=AIRCRAFT,
        observed_at=later,
    )
    db_session.commit()

    assert first.id == second.id
    assert second.first_seen_at == first_seen
    assert second.last_seen_at == later
    assert db_session.query(DeviceTopology).count() == 1


def test_an_older_observation_does_not_rewind_the_clock(db_session, workspace):
    """Reprocesar un mensaje viejo no debe hacer parecer que el equipo no se ha
    visto desde entonces."""
    now = datetime.now(UTC)
    record_topology(
        db_session,
        workspace_id=workspace.id,
        gateway_serial=GATEWAY,
        aircraft_serial=AIRCRAFT,
        observed_at=now,
    )
    db_session.commit()

    replayed = record_topology(
        db_session,
        workspace_id=workspace.id,
        gateway_serial=GATEWAY,
        aircraft_serial=AIRCRAFT,
        observed_at=now - timedelta(days=1),
    )
    db_session.commit()

    assert replayed.last_seen_at == now


def test_a_payload_swap_is_a_different_combination(db_session, workspace):
    record_topology(
        db_session,
        workspace_id=workspace.id,
        gateway_serial=GATEWAY,
        aircraft_serial=AIRCRAFT,
    )
    record_topology(
        db_session,
        workspace_id=workspace.id,
        gateway_serial=GATEWAY,
        aircraft_serial=AIRCRAFT,
        payload_serial="H20T0000000001",
    )
    db_session.commit()

    # Dos filas, no una actualizada: cambiar el payload es información, no ruido.
    assert db_session.query(DeviceTopology).count() == 2


def test_a_known_serial_is_linked_to_its_device(db_session, workspace, make_device):
    aircraft = make_device(serial=AIRCRAFT, kind=DeviceKind.AIRCRAFT, model="Mavic 3E")
    controller = make_device(serial=GATEWAY, kind=DeviceKind.CONTROLLER, model="RC Pro")

    topology = record_topology(
        db_session,
        workspace_id=workspace.id,
        gateway_serial=AIRCRAFT.lower(),  # normalización de por medio
        aircraft_serial=AIRCRAFT,
    )
    db_session.commit()

    assert topology.aircraft_device_id == aircraft.id
    # El gateway se pasó con el serial de la aeronave: existe en el workspace pero
    # con otro `kind`, así que no se enlaza. Enlazarlo sería un error silencioso.
    assert topology.gateway_device_id is None
    assert controller.id is not None


def test_an_unknown_serial_is_still_recorded_and_queued(db_session, workspace):
    """AL-R4: nunca se descarta una observación por no poder resolver la aeronave.
    El padrón es de AeroControl y puede no responder, estar vacío o discrepar."""
    topology = record_topology(
        db_session,
        workspace_id=workspace.id,
        gateway_serial=GATEWAY,
        aircraft_serial="1582F5FHD24A00000009",  # difiere en un carácter, a propósito
    )
    db_session.commit()

    assert topology.aircraft_device_id is None
    pending = unresolved_topologies(db_session, workspace_id=workspace.id)
    assert [item.id for item in pending] == [topology.id]


def test_a_half_identified_observation_is_refused(db_session, workspace):
    with pytest.raises(TopologyError):
        record_topology(
            db_session,
            workspace_id=workspace.id,
            gateway_serial=GATEWAY,
            aircraft_serial="   ",
        )


def test_a_human_correction_is_marked_as_such(db_session, workspace):
    topology = record_topology(
        db_session,
        workspace_id=workspace.id,
        gateway_serial=GATEWAY,
        aircraft_serial=AIRCRAFT,
        source="manual",
        metadata={"resuelto_por": "certificado RPAS DGAC"},
    )
    db_session.commit()

    # Una corrección a mano no debe poder confundirse con algo que DJI reportó.
    assert topology.source == "manual"
    assert topology.metadata_json["resuelto_por"] == "certificado RPAS DGAC"

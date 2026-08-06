from sqlalchemy import UniqueConstraint

from aerolink.db import Base
from aerolink.models import Device, FlightSession


def test_domain_tables_are_registered() -> None:
    assert {"devices", "flight_sessions", "raw_messages"}.issubset(Base.metadata.tables)


def test_device_serial_is_unique_per_workspace() -> None:
    constraints = [
        c for c in Device.__table__.constraints if isinstance(c, UniqueConstraint)
    ]

    assert any(
        tuple(c.columns.keys()) == ("workspace_id", "serial_number")
        for c in constraints
    )


def test_flight_external_reference_is_idempotent_per_workspace() -> None:
    constraints = [
        c
        for c in FlightSession.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]

    assert any(
        tuple(c.columns.keys()) == ("workspace_id", "external_reference")
        for c in constraints
    )

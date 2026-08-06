from sqlalchemy import UniqueConstraint

from aerolink.db import Base
from aerolink.models import Device, FlightEvidence, FlightSession, UserIdentity


def test_domain_tables_are_registered() -> None:
    assert {
        "devices",
        "flight_evidence",
        "flight_sessions",
        "raw_messages",
        "telemetry_samples",
        "user_identities",
    }.issubset(Base.metadata.tables)


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


def test_identity_and_evidence_have_workspace_scoped_unique_constraints() -> None:
    identity_constraints = [
        c for c in UserIdentity.__table__.constraints if isinstance(c, UniqueConstraint)
    ]
    evidence_constraints = [
        c
        for c in FlightEvidence.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]

    assert any(
        tuple(c.columns.keys()) == ("workspace_id", "provider", "subject")
        for c in identity_constraints
    )
    assert any(
        tuple(c.columns.keys()) == ("workspace_id", "sha256")
        for c in evidence_constraints
    )

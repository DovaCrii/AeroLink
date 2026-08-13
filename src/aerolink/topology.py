"""Recording the observed control–aircraft–payload topology (AL-203).

The writer for `DeviceTopology`. Three rules, and every one of them exists because
the obvious alternative loses data or invents it:

**Normalize, then compare exactly.** `normalize_serial` (ADR-0002 §2) upper-cases
and strips whitespace, and that is the *whole* of the matching. No fuzzy matching:
of the sixteen real aircraft in AeroControl's padrón, two differ from their
documentation by a single character (`O`↔`0`, `1581…` vs `1582…`), so a "helpful"
approximate match would attribute a flight to the wrong airframe. Wrong
attribution is worse than no attribution, which is what the exceptions tray is
for (AL-306).

**An unresolvable serial is still an observation.** If no local `Device` carries
the serial, the row is written anyway with the device links left null. AL-R4 is
explicit: never discard telemetry because the aircraft could not be resolved —
reconcile later. The padrón belongs to AeroControl, and it can be reached, empty,
or wrong at the moment a message arrives.

**Seeing the same combination again is an update, not a new row.** `last_seen_at`
moves; nothing else does. That keeps a payload swap visible as news instead of
buried under identical rows.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from aerolink.models import Device, DeviceKind, DeviceTopology
from aerolink.serials import normalize_serial
from aerolink.timeutils import as_utc

logger = logging.getLogger("aerolink.topology")


class TopologyError(ValueError):
    """Raised when an observation cannot identify the aircraft or the gateway."""


def _resolve_device(
    session: Session, *, workspace_id: uuid.UUID, serial: str, kind: DeviceKind
) -> Device | None:
    """The local `Device` with this exact normalized serial, or None.

    Filtered by kind as well as serial: a serial that exists in the workspace but
    belongs to a battery is not the aircraft, and linking it would be a silent
    error rather than a missing link.
    """
    if not serial:
        return None
    return session.scalars(
        select(Device).where(
            Device.workspace_id == workspace_id,
            Device.serial_number == serial,
            Device.kind == kind,
        )
    ).one_or_none()


def record_topology(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    gateway_serial: str,
    aircraft_serial: str,
    payload_serial: str | None = None,
    source: str = "dji",
    observed_at: datetime | None = None,
    metadata: dict | None = None,
) -> DeviceTopology:
    """Record (or refresh) one observed combination. The caller commits."""
    gateway = normalize_serial(gateway_serial)
    aircraft = normalize_serial(aircraft_serial)
    payload = normalize_serial(payload_serial)
    if not gateway or not aircraft:
        # Refusing here rather than storing a half-identified row: a topology
        # without both ends cannot be reconciled with anything later, and it
        # would occupy the unique constraint with a combination nobody can use.
        raise TopologyError(
            "a topology observation needs both a gateway and an aircraft serial"
        )

    seen_at = observed_at or datetime.now(UTC)
    existing = session.scalars(
        select(DeviceTopology).where(
            DeviceTopology.workspace_id == workspace_id,
            DeviceTopology.gateway_serial == gateway,
            DeviceTopology.aircraft_serial == aircraft,
            DeviceTopology.payload_serial == payload,
        )
    ).one_or_none()

    if existing is not None:
        # Monotonic on purpose: replaying an older message must not rewind the
        # clock on a combination that has been seen more recently. `as_utc` is
        # not decoration -- comparing a stored timestamp with an aware one raises
        # TypeError when the driver returns it naive.
        existing.last_seen_at = max(as_utc(existing.last_seen_at), seen_at)
        return existing

    topology = DeviceTopology(
        workspace_id=workspace_id,
        gateway_serial=gateway,
        aircraft_serial=aircraft,
        payload_serial=payload,
        gateway_device_id=getattr(
            _resolve_device(
                session,
                workspace_id=workspace_id,
                serial=gateway,
                kind=DeviceKind.CONTROLLER,
            ),
            "id",
            None,
        ),
        aircraft_device_id=getattr(
            _resolve_device(
                session,
                workspace_id=workspace_id,
                serial=aircraft,
                kind=DeviceKind.AIRCRAFT,
            ),
            "id",
            None,
        ),
        first_seen_at=seen_at,
        last_seen_at=seen_at,
        source=source,
        metadata_json=metadata or {},
    )
    session.add(topology)
    logger.info(
        "topology_observed",
        extra={
            "workspace_id": str(workspace_id),
            "topic": f"{gateway}/{aircraft}/{payload or '-'}",
        },
    )
    return topology


def unresolved_topologies(
    session: Session, *, workspace_id: uuid.UUID
) -> list[DeviceTopology]:
    """Observations whose aircraft serial matched no local device.

    The queue a person has to settle against the DGAC certificate — the padrón
    disagreement is a fact about the fleet, not a bug to patch with a looser
    comparison.
    """
    return list(
        session.scalars(
            select(DeviceTopology).where(
                DeviceTopology.workspace_id == workspace_id,
                DeviceTopology.aircraft_device_id.is_(None),
            )
        )
    )

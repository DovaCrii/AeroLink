"""AL-107: the device inventory AeroControl mirrors (ADR-0002 fase 2, ADR-0003).

Exposes **only what AeroLink masters** — batteries, payloads and controller
topology. Aircraft are AeroControl's padrón (ADR-0002 §3) and asking for them
here is a 403, not an empty list: `AL-R4` says "no duplicar el padrón", and the
way that rule survives contact with a hurry is as an assertion a test checks,
not a paragraph in a document.

No pagination, on purpose. The consumer reads one response and never looks for a
next page; if this paginated, AeroControl would mirror page one and report every
remaining battery as "not in this feed" — a warning indistinguishable from an
inventory that is genuinely shrinking. Revisit above ~1000 devices, and note
that adding pagination is a contract change where the consumer ships first.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from aerolink.audit import record_audit
from aerolink.auth import ServiceCaller, require_service_token
from aerolink.db import get_db
from aerolink.models import Device, DeviceKind, Workspace
from aerolink.schemas import DeviceInventoryItem, DeviceInventoryResponse
from aerolink.serials import normalize_serial

logger = logging.getLogger("aerolink.inventory")

router = APIRouter(prefix="/api/v1", tags=["inventory"])

# ADR-0002 §3, fourth row: the domains AeroLink masters. `AIRCRAFT` is absent
# and that absence is the point.
EXPORTABLE_KINDS = frozenset(
    {DeviceKind.BATTERY, DeviceKind.PAYLOAD, DeviceKind.CONTROLLER}
)

# Free-form `Device.status` mapped onto the two values AeroControl understands.
# Anything unrecognized is omitted rather than guessed: the consumer keeps what
# it knew, which beats being told something wrong.
_STATUS_MAP = {
    "active": "active",
    "online": "active",
    "in_service": "active",
    "retired": "retired",
    "decommissioned": "retired",
}


@router.get(
    # Declared *with* the trailing slash: the consumer builds
    # ".../devices/?kind=...", and declaring "/devices" would make Starlette
    # answer every single call with a 307 that merely happens to work.
    "/devices/",
    response_model=DeviceInventoryResponse,
    response_model_exclude_none=True,
    summary="Inventario de dispositivos que AeroLink masterea",
)
def list_devices(
    request: Request,
    response: Response,
    # Annotated rather than call-in-default: it is FastAPI's current idiom and
    # it keeps ruff's B008 quiet without disabling the rule repo-wide.
    kind: Annotated[DeviceKind, Query(description="battery | payload | controller")],
    caller: Annotated[ServiceCaller, Depends(require_service_token)],
    session: Annotated[Session, Depends(get_db)],
) -> DeviceInventoryResponse:
    """Return the inventory for one device kind, scoped to the caller's workspace."""
    if kind not in EXPORTABLE_KINDS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "aircraft are AeroControl's padrón, not AeroLink's (ADR-0002 §3, AL-R4)"
            ),
        )

    workspace = session.scalar(
        select(Workspace).where(Workspace.slug == caller.workspace_slug)
    )
    if workspace is None:
        # 503, not an empty list: an unresolvable workspace is a configuration
        # fault, and answering `{"results": []}` would be indistinguishable from
        # a genuinely empty inventory -- a quiet lie the consumer would mirror.
        logger.error(
            "service_workspace_unresolved", extra={"slug": caller.workspace_slug}
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="integration workspace not configured",
        )

    devices = session.scalars(
        select(Device)
        .where(Device.workspace_id == workspace.id, Device.kind == kind)
        # Deterministic, so a normalization collision resolves the same way on
        # every run instead of depending on row order.
        .order_by(Device.serial_number, Device.id)
    ).all()

    items, collisions = _to_items(devices)

    record_audit(
        session,
        workspace_id=workspace.id,
        actor_subject=caller.subject,
        action="inventory.read",
        resource_type="device",
        metadata={
            "kind": kind.value,
            "count": len(items),
            "workspace_slug": caller.workspace_slug,
            # Ties this row to the access-log line the middleware already emits.
            "request_id": request.headers.get("X-Request-ID", ""),
            "collisions": collisions,
        },
    )
    # Committed before the response is returned: if the disclosure cannot be
    # recorded, it does not happen. A full disk stops the sync, which is the
    # honest trade -- see ADR-0003.
    session.commit()

    # The body carries equipment serials.
    response.headers["Cache-Control"] = "no-store"
    return DeviceInventoryResponse(results=items, count=len(items))


def _to_items(devices) -> tuple[list[DeviceInventoryItem], list[str]]:
    """Map rows onto the contract, dropping what cannot be trusted.

    `metadata_json` is untyped, so every value is validated rather than passed
    through: AeroControl silently ignores a value of the wrong type, so passing
    `"120"` for a cycle count would make the number vanish with no error on
    either side.
    """
    items: list[DeviceInventoryItem] = []
    seen: set[str] = set()
    collisions: list[str] = []

    for device in devices:
        serial = normalize_serial(device.serial_number)
        if not serial:
            logger.warning("device_without_serial", extra={"device": str(device.id)})
            continue
        if serial in seen:
            # Two stored rows normalized to the same serial. Emitting both would
            # let the consumer's last write win nondeterministically.
            collisions.append(serial)
            logger.warning("serial_collision", extra={"serial": serial})
            continue
        seen.add(serial)

        metadata = device.metadata_json or {}
        items.append(
            DeviceInventoryItem(
                serial_number=serial,
                model=device.model or None,
                status=_STATUS_MAP.get((device.status or "").lower()),
                cycle_count=_as_count(metadata.get("cycle_count")),
                health_percent=_as_percent(metadata.get("health_percent")),
                firmware_version=_as_text(metadata.get("firmware_version"), 50),
                aircraft_serial=normalize_serial(metadata.get("aircraft_serial"))
                or None,
            )
        )
    return items, collisions


def _as_count(value) -> int | None:
    # `isinstance(True, int)` is True in Python, so an errant boolean would
    # arrive as cycle_count=1 and look like real data.
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _as_percent(value) -> int | None:
    # Out of range is dropped, not clamped: 150 is an upstream bug, and clamping
    # it to 100 would launder that bug into a plausible health reading.
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value <= 100 else None


def _as_text(value, limit: int) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    # Truncated here as well as on the consumer, so both sides store the same
    # string rather than two different prefixes.
    return value.strip()[:limit]

"""The wire contract with AeroControl (ADR-0002 fase 2b).

This is the contract; how the values are stored is an implementation detail.
Today cycles, health and firmware live in `Device.metadata_json` because the
`devices` table is empty until `AL-203` and no real DJI payload has been seen
yet — choosing columns now would mean guessing names and types and paying a
second migration. When `AL-204` delivers real fixtures and the fields prove
stable, they become columns and **nothing here moves**.

Optional fields are omitted from the response rather than sent as `null`: the
consumer treats an absent key as "AeroLink did not say" and keeps whatever it
already knows, which is not the same as being told the value is zero.
"""

from pydantic import BaseModel, Field


class DeviceInventoryItem(BaseModel):
    """One device AeroLink masters, in AeroControl's vocabulary."""

    serial_number: str = Field(description="Normalized per ADR-0002 §2.")
    model: str | None = None
    status: str | None = Field(
        default=None, description="active | retired. Omitted when unknown."
    )
    cycle_count: int | None = None
    health_percent: int | None = None
    firmware_version: str | None = None
    aircraft_serial: str | None = Field(
        default=None, description="Last seen on this airframe, if known."
    )


class DeviceInventoryResponse(BaseModel):
    """Enveloped, not a bare list.

    The consumer accepts either, but the envelope leaves room to add fields
    without breaking it, and a top-level JSON array is a legacy hijacking
    footgun not worth inheriting. `count` is redundant with `len(results)` on
    purpose: it makes the audit row cross-checkable against what went out.
    """

    results: list[DeviceInventoryItem]
    count: int

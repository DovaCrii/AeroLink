import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aerolink.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def _enum_values(enum_class) -> list[str]:
    """Persist the enum's **values**, not its member names.

    SQLAlchemy's default for `Enum(PyEnum)` is to store `member.name`, so
    `DeviceKind.BATTERY` would be sent as `"BATTERY"`. The initial migration
    created the Postgres types with the lower-case *values*
    (`sa.Enum("controller", "aircraft", "payload", "battery", name="device_kind")`),
    so the default makes every query fail with `invalid input value for enum`.

    That mismatch reached production on 2026-08-13 —`?kind=battery` answered 500 on
    p340— because sqlite degrades `Enum` to VARCHAR and both sides agreed on the
    name, so the whole suite passed. The values are also what the HTTP contract and
    the audit rows use (`kind.value`), which makes them the right side to keep.
    """
    return [member.value for member in enum_class]


class DeviceKind(str, enum.Enum):
    CONTROLLER = "controller"
    AIRCRAFT = "aircraft"
    PAYLOAD = "payload"
    BATTERY = "battery"


class UserRole(str, enum.Enum):
    ADMINISTRATOR = "administrator"
    OPERATIONS = "operations"
    PILOT = "pilot"
    VIEWER = "viewer"


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    devices: Mapped[list["Device"]] = relationship(back_populates="workspace")


class UserIdentity(Base):
    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "provider", "subject", name="uq_identity_workspace_subject"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), index=True
    )
    provider: Mapped[str] = mapped_column(String(50), default="entra")
    subject: Mapped[str] = mapped_column(String(200), index=True)
    display_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=_enum_values)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "serial_number", name="uq_device_workspace_serial"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), index=True
    )
    kind: Mapped[DeviceKind] = mapped_column(
        Enum(DeviceKind, name="device_kind", values_callable=_enum_values)
    )
    serial_number: Mapped[str] = mapped_column(String(120), index=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="unknown", index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    workspace: Mapped[Workspace] = relationship(back_populates="devices")


class DeviceTopology(Base):
    """Which controller flew which aircraft with which payload, as *observed* (AL-203).

    Keyed on **serials**, not on local UUIDs. The serial is the only key present in
    DJI's telemetry, AeroControl's padrón and the DGAC certificate (AL-R3), and a
    UUID minted here would be resolvable by nobody else. The `*_device_id` columns
    are a convenience for when the serial happens to match a known `Device`; they
    are nullable because AL-R4 requires the opposite failure mode from the obvious
    one — **an unresolvable serial is kept, never discarded**. Losing the link is
    recoverable later; losing the observation is not.

    One row per distinct combination, with `first_seen_at`/`last_seen_at` instead of
    one row per message: the fleet has a handful of airframes and a payload swap is
    news, while ten thousand identical rows are not.
    """

    __tablename__ = "device_topologies"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "gateway_serial",
            "aircraft_serial",
            "payload_serial",
            name="uq_topology_workspace_combination",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), index=True
    )
    # The controller/gateway DJI reports as the origin of the messages.
    gateway_serial: Mapped[str] = mapped_column(String(120), index=True)
    aircraft_serial: Mapped[str] = mapped_column(String(120), index=True)
    # Empty string rather than NULL: it is part of the unique constraint, and in
    # SQL two NULLs are never equal, so a nullable column would let the same
    # payload-less combination be inserted without limit.
    payload_serial: Mapped[str] = mapped_column(String(120), default="")
    gateway_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id"), nullable=True
    )
    aircraft_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id"), nullable=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    # "dji" for something the telemetry reported, anything else for a human
    # correction -- so a fix entered by hand is never mistaken for an observation.
    source: Mapped[str] = mapped_column(String(30), default="dji", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RawMessage(Base):
    __tablename__ = "raw_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id"), nullable=True, index=True
    )
    topic: Mapped[str] = mapped_column(String(500), index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    device_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    qos: Mapped[int] = mapped_column(default=0)
    payload_json: Mapped[dict] = mapped_column(JSON)
    payload_sha256: Mapped[str] = mapped_column(String(64), index=True)


class TelemetrySample(Base):
    __tablename__ = "telemetry_samples"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"), index=True)
    flight_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("flight_sessions.id"), nullable=True, index=True
    )
    raw_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("raw_messages.id"), nullable=True, index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    altitude_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    ground_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_json: Mapped[dict] = mapped_column(JSON, default=dict)


class FlightSession(Base):
    __tablename__ = "flight_sessions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "external_reference",
            name="uq_flight_workspace_external_ref",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), index=True
    )
    external_reference: Mapped[str] = mapped_column(String(180))
    pilot_subject: Mapped[str | None] = mapped_column(
        String(200), nullable=True, index=True
    )
    aircraft_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), default="detected", index=True)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class FlightEvidence(Base):
    __tablename__ = "flight_evidence"
    __table_args__ = (
        UniqueConstraint("workspace_id", "sha256", name="uq_evidence_workspace_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), index=True
    )
    flight_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("flight_sessions.id"), nullable=True, index=True
    )
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    status: Mapped[str] = mapped_column(String(30), default="received", index=True)


class IngestionException(Base):
    __tablename__ = "ingestion_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), index=True
    )
    kind: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    message: Mapped[str] = mapped_column(Text)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id"), nullable=True, index=True
    )
    actor_subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

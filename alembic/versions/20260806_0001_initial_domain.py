"""Create AeroLink's initial standalone operational domain.

Revision ID: 20260806_0001
Revises:
Create Date: 2026-08-06 15:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


device_kind = sa.Enum(
    "controller", "aircraft", "payload", "battery", name="device_kind"
)
user_role = sa.Enum("administrator", "operations", "pilot", "viewer", name="user_role")


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "user_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("role", user_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "provider", "subject", name="uq_identity_workspace_subject"
        ),
    )
    op.create_index(
        "ix_user_identities_workspace_id", "user_identities", ["workspace_id"]
    )
    op.create_index("ix_user_identities_subject", "user_identities", ["subject"])
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("kind", device_kind, nullable=False),
        sa.Column("serial_number", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "serial_number", name="uq_device_workspace_serial"
        ),
    )
    op.create_index("ix_devices_workspace_id", "devices", ["workspace_id"])
    op.create_index("ix_devices_serial_number", "devices", ["serial_number"])
    op.create_index("ix_devices_status", "devices", ["status"])
    op.create_table(
        "raw_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qos", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_messages_workspace_id", "raw_messages", ["workspace_id"])
    op.create_index("ix_raw_messages_device_id", "raw_messages", ["device_id"])
    op.create_index("ix_raw_messages_topic", "raw_messages", ["topic"])
    op.create_index("ix_raw_messages_received_at", "raw_messages", ["received_at"])
    op.create_index(
        "ix_raw_messages_payload_sha256", "raw_messages", ["payload_sha256"]
    )
    op.create_table(
        "flight_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("external_reference", sa.String(length=180), nullable=False),
        sa.Column("pilot_subject", sa.String(length=200), nullable=True),
        sa.Column("aircraft_device_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["aircraft_device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "external_reference",
            name="uq_flight_workspace_external_ref",
        ),
    )
    op.create_index(
        "ix_flight_sessions_workspace_id", "flight_sessions", ["workspace_id"]
    )
    op.create_index(
        "ix_flight_sessions_pilot_subject", "flight_sessions", ["pilot_subject"]
    )
    op.create_index("ix_flight_sessions_status", "flight_sessions", ["status"])
    op.create_table(
        "telemetry_samples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("flight_session_id", sa.Uuid(), nullable=True),
        sa.Column("raw_message_id", sa.Uuid(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("altitude_m", sa.Float(), nullable=True),
        sa.Column("ground_speed_mps", sa.Float(), nullable=True),
        sa.Column("sample_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["flight_session_id"], ["flight_sessions.id"]),
        sa.ForeignKeyConstraint(["raw_message_id"], ["raw_messages.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telemetry_samples_workspace_id", "telemetry_samples", ["workspace_id"]
    )
    op.create_index(
        "ix_telemetry_samples_device_id", "telemetry_samples", ["device_id"]
    )
    op.create_index(
        "ix_telemetry_samples_flight_session_id",
        "telemetry_samples",
        ["flight_session_id"],
    )
    op.create_index(
        "ix_telemetry_samples_raw_message_id", "telemetry_samples", ["raw_message_id"]
    )
    op.create_index(
        "ix_telemetry_samples_recorded_at", "telemetry_samples", ["recorded_at"]
    )
    op.create_table(
        "flight_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("flight_session_id", sa.Uuid(), nullable=True),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["flight_session_id"], ["flight_sessions.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint(
            "workspace_id", "sha256", name="uq_evidence_workspace_sha256"
        ),
    )
    op.create_index(
        "ix_flight_evidence_workspace_id", "flight_evidence", ["workspace_id"]
    )
    op.create_index(
        "ix_flight_evidence_flight_session_id", "flight_evidence", ["flight_session_id"]
    )
    op.create_index("ix_flight_evidence_sha256", "flight_evidence", ["sha256"])
    op.create_index("ix_flight_evidence_status", "flight_evidence", ["status"])
    op.create_table(
        "ingestion_exceptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_exceptions_workspace_id", "ingestion_exceptions", ["workspace_id"]
    )
    op.create_index("ix_ingestion_exceptions_kind", "ingestion_exceptions", ["kind"])
    op.create_index(
        "ix_ingestion_exceptions_status", "ingestion_exceptions", ["status"]
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("actor_subject", sa.String(length=200), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_workspace_id", "audit_events", ["workspace_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    for table_name in (
        "audit_events",
        "ingestion_exceptions",
        "flight_evidence",
        "telemetry_samples",
        "flight_sessions",
        "raw_messages",
        "devices",
        "user_identities",
        "workspaces",
    ):
        op.drop_table(table_name)
    user_role.drop(op.get_bind(), checkfirst=True)
    device_kind.drop(op.get_bind(), checkfirst=True)

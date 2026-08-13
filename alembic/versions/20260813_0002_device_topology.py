"""Add the observed device topology (AL-203).

`ARCHITECTURE.md` listed `DeviceTopology` among AeroLink's own data since the
beginning and it never existed: no model, no table, no references. The barrido of
2026-08-13 found it. This is the table.

Revision ID: 20260813_0002
Revises: 20260806_0001
Create Date: 2026-08-13 16:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_0002"
down_revision: str | None = "20260806_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_topologies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("gateway_serial", sa.String(length=120), nullable=False),
        sa.Column("aircraft_serial", sa.String(length=120), nullable=False),
        # Not nullable: it is part of the unique constraint below, and two NULLs
        # never compare equal, so a nullable column would allow unlimited
        # duplicates of the same payload-less combination.
        sa.Column("payload_serial", sa.String(length=120), nullable=False),
        sa.Column("gateway_device_id", sa.Uuid(), nullable=True),
        sa.Column("aircraft_device_id", sa.Uuid(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["gateway_device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["aircraft_device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "gateway_serial",
            "aircraft_serial",
            "payload_serial",
            name="uq_topology_workspace_combination",
        ),
    )
    op.create_index(
        "ix_device_topologies_workspace_id", "device_topologies", ["workspace_id"]
    )
    op.create_index(
        "ix_device_topologies_gateway_serial", "device_topologies", ["gateway_serial"]
    )
    op.create_index(
        "ix_device_topologies_aircraft_serial", "device_topologies", ["aircraft_serial"]
    )
    op.create_index(
        "ix_device_topologies_last_seen_at", "device_topologies", ["last_seen_at"]
    )
    op.create_index("ix_device_topologies_source", "device_topologies", ["source"])


def downgrade() -> None:
    op.drop_index("ix_device_topologies_source", table_name="device_topologies")
    op.drop_index("ix_device_topologies_last_seen_at", table_name="device_topologies")
    op.drop_index(
        "ix_device_topologies_aircraft_serial", table_name="device_topologies"
    )
    op.drop_index("ix_device_topologies_gateway_serial", table_name="device_topologies")
    op.drop_index("ix_device_topologies_workspace_id", table_name="device_topologies")
    op.drop_table("device_topologies")

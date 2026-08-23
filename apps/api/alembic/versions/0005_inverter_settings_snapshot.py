"""Add inverter_settings_snapshot table for the 0x4000 settings block.

Revision ID: 0005_inverter_settings_snapshot
Revises: 0004_grid_source_metrics
Create Date: 2026-08-23
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_inverter_settings_snapshot"
down_revision = "0004_grid_source_metrics"
branch_labels = None
depends_on = None


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    json_type = _json_type()
    # See 0002_bms_telemetry for why id_type must resolve to plain INTEGER on
    # SQLite rather than a bare BigInteger -- bare BIGINT never wires up
    # SQLite's ROWID autoincrement.
    id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "inverter_settings_snapshot",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column("sample_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("raw_registers", json_type, nullable=False),
        sa.Column(
            "register_map_version",
            sa.String(length=32),
            nullable=False,
            server_default="prime-settings-v1",
        ),
        sa.Column("gateway_version", sa.String(length=32), nullable=True),
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
            server_default="usb-rs485-laptop",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sample_id"),
    )
    op.create_index(
        "ix_inverter_settings_device_recorded",
        "inverter_settings_snapshot",
        ["device_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inverter_settings_device_recorded", table_name="inverter_settings_snapshot"
    )
    op.drop_table("inverter_settings_snapshot")

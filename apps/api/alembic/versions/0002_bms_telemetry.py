"""Add bms_telemetry table for JK BMS (second battery) readings.

Revision ID: 0002_bms_telemetry
Revises: 0001_initial
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_bms_telemetry"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bms_telemetry",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sample_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cell_count", sa.Integer(), nullable=True),
        sa.Column("cell_voltages_mv", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pack_voltage_v", sa.Float(), nullable=True),
        sa.Column("pack_power_w", sa.Float(), nullable=True),
        sa.Column("pack_current_a", sa.Float(), nullable=True),
        sa.Column("temperature_1_c", sa.Float(), nullable=True),
        sa.Column("temperature_2_c", sa.Float(), nullable=True),
        sa.Column("soc_percent", sa.Float(), nullable=True),
        sa.Column("remaining_capacity_ah", sa.Float(), nullable=True),
        sa.Column("full_capacity_ah", sa.Float(), nullable=True),
        sa.Column("cycle_count", sa.Integer(), nullable=True),
        sa.Column("balance_current_a", sa.Float(), nullable=True),
        sa.Column("alarm_flags", sa.BigInteger(), nullable=True),
        sa.Column("raw_registers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("register_map_version", sa.String(length=32), nullable=False),
        sa.Column("decoder_version", sa.String(length=32), nullable=True),
        sa.Column("quality_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quality_details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("gateway_version", sa.String(length=32), nullable=True),
        sa.Column("gateway_boot_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sample_id"),
    )
    op.create_index(
        "ix_bms_telemetry_device_recorded", "bms_telemetry", ["device_id", "recorded_at"]
    )
    op.create_index(
        "ix_bms_telemetry_device_received", "bms_telemetry", ["device_id", "received_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_bms_telemetry_device_received", table_name="bms_telemetry")
    op.drop_index("ix_bms_telemetry_device_recorded", table_name="bms_telemetry")
    op.drop_table("bms_telemetry")

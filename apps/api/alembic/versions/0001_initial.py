"""Initial PLTS monitoring schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-02
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("inverter_model", sa.String(length=100), nullable=True),
        sa.Column("inverter_rated_w", sa.Integer(), nullable=False),
        sa.Column("pv_rated_wp", sa.Integer(), nullable=False),
        sa.Column("battery_nominal_v", sa.Float(), nullable=True),
        sa.Column("battery_capacity_ah", sa.Float(), nullable=True),
        sa.Column("tariff_idr_per_kwh", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_gateway_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_telemetry_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "device_api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("key_prefix", sa.String(length=20), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_device_api_keys_device_id", "device_api_keys", ["device_id"])
    op.create_index("ix_device_api_keys_key_prefix", "device_api_keys", ["key_prefix"])
    op.create_table(
        "inverter_telemetry",
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
        sa.Column("pv_voltage_v", sa.Float(), nullable=True),
        sa.Column("pv_current_a", sa.Float(), nullable=True),
        sa.Column("pv_power_w", sa.Float(), nullable=True),
        sa.Column("battery_voltage_v", sa.Float(), nullable=True),
        sa.Column("ac_output_voltage_v", sa.Float(), nullable=True),
        sa.Column("ac_output_current_a", sa.Float(), nullable=True),
        sa.Column("ac_output_power_w", sa.Float(), nullable=True),
        sa.Column("load_percent", sa.Float(), nullable=True),
        sa.Column("inverter_temperature_c", sa.Float(), nullable=True),
        sa.Column("raw_registers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_start_address", sa.Integer(), nullable=False),
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
        "ix_telemetry_device_recorded", "inverter_telemetry", ["device_id", "recorded_at"]
    )
    op.create_index(
        "ix_telemetry_device_received", "inverter_telemetry", ["device_id", "received_at"]
    )
    op.create_table(
        "gateway_status",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("gateway_boot_id", sa.Uuid(), nullable=True),
        sa.Column("gateway_version", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_serial_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queue_depth", sa.Integer(), nullable=False),
        sa.Column("serial_status", sa.String(length=32), nullable=False),
        sa.Column("api_status", sa.String(length=32), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("device_id"),
    )
    op.create_table(
        "ingest_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingest_events_device_id", "ingest_events", ["device_id"])
    op.create_table(
        "hourly_summaries",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pv_energy_wh", sa.Float(), nullable=False),
        sa.Column("ac_output_energy_wh", sa.Float(), nullable=False),
        sa.Column("estimated_surplus_wh", sa.Float(), nullable=False),
        sa.Column("avg_pv_power_w", sa.Float(), nullable=True),
        sa.Column("max_pv_power_w", sa.Float(), nullable=True),
        sa.Column("avg_ac_output_power_w", sa.Float(), nullable=True),
        sa.Column("max_ac_output_power_w", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("valid_interval_seconds", sa.Float(), nullable=False),
        sa.Column("coverage_percent", sa.Float(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("device_id", "bucket_start"),
    )
    op.create_table(
        "daily_summaries",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("device_id", "local_date"),
        sa.UniqueConstraint("device_id", "local_date"),
    )


def downgrade() -> None:
    op.drop_table("daily_summaries")
    op.drop_table("hourly_summaries")
    op.drop_index("ix_ingest_events_device_id", table_name="ingest_events")
    op.drop_table("ingest_events")
    op.drop_table("gateway_status")
    op.drop_index("ix_telemetry_device_received", table_name="inverter_telemetry")
    op.drop_index("ix_telemetry_device_recorded", table_name="inverter_telemetry")
    op.drop_table("inverter_telemetry")
    op.drop_index("ix_device_api_keys_key_prefix", table_name="device_api_keys")
    op.drop_index("ix_device_api_keys_device_id", table_name="device_api_keys")
    op.drop_table("device_api_keys")
    op.drop_table("devices")
